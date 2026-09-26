"""Workflow CRUD, versioning, validation and run endpoints (spec sections 12/20/23/29)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import DbSession
from app.modules.workflows.engine import WorkflowEngine
from app.modules.communications.service import get_communication_service
from app.modules.ai.service import get_ai_service
from app.modules.workflows.models import WorkflowRun
from app.modules.workflows.registry import list_node_metadata
from app.modules.workflows.schemas import (
    TestRunRequest,
    ValidationIssue,
    ValidationReport,
    VersionCreate,
    WorkflowCreate,
    WorkflowDefinition,
    WorkflowOut,
    WorkflowRunOut,
    WorkflowUpdate,
)
from app.modules.workflows.service import WorkflowService
from app.modules.workflows.validator import validate_workflow

router = APIRouter(prefix="/workflows", tags=["workflows"])


async def get_service(db: DbSession) -> WorkflowService:
    engine = WorkflowEngine(db, get_ai_service(), get_communication_service())
    return WorkflowService(db, engine)


ServiceDep = Annotated[WorkflowService, Depends(get_service)]


@router.get("/node-types")
async def node_types() -> list[dict]:
    """Node metadata for the builder palette and inspector."""
    return list_node_metadata()


@router.get("", response_model=list[WorkflowOut])
async def list_workflows(service: ServiceDep) -> list[WorkflowOut]:
    workflows = await service.list_workflows()
    return [WorkflowOut.model_validate(w, from_attributes=True) for w in workflows]


@router.post("", response_model=WorkflowOut, status_code=status.HTTP_201_CREATED)
async def create_workflow(data: WorkflowCreate, service: ServiceDep) -> WorkflowOut:
    workflow = await service.create_workflow(data)
    workflow = await service.get_workflow(workflow.id, fresh=True)  # re-fetch with versions eager-loaded
    assert workflow is not None
    return WorkflowOut.model_validate(workflow, from_attributes=True)


@router.get("/{workflow_id}", response_model=WorkflowOut)
async def get_workflow(workflow_id: int, service: ServiceDep) -> WorkflowOut:
    workflow = await service.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")
    return WorkflowOut.model_validate(workflow, from_attributes=True)


@router.patch("/{workflow_id}", response_model=WorkflowOut)
async def update_workflow(workflow_id: int, data: WorkflowUpdate, service: ServiceDep) -> WorkflowOut:
    workflow = await service.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")
    await service.update_workflow(workflow, data)
    return WorkflowOut.model_validate(workflow, from_attributes=True)


@router.post("/{workflow_id}/versions", response_model=WorkflowOut)
async def save_version(workflow_id: int, data: VersionCreate, service: ServiceDep) -> WorkflowOut:
    """Save the builder definition as a new immutable version (spec section 31)."""
    workflow = await service.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")
    await service.save_version(workflow, data.definition, data.comment)
    workflow = await service.get_workflow(workflow_id, fresh=True)  # re-fetch so current_version is fresh
    assert workflow is not None
    return WorkflowOut.model_validate(workflow, from_attributes=True)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(workflow_id: int, service: ServiceDep) -> None:
    if not await service.delete_workflow(workflow_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")


@router.post("/validate", response_model=ValidationReport)
async def validate_definition(definition: WorkflowDefinition) -> ValidationReport:
    return validate_workflow(definition)


@router.post("/{workflow_id}/validate", response_model=ValidationReport)
async def validate_workflow_id(workflow_id: int, service: ServiceDep) -> ValidationReport:
    workflow = await service.get_workflow(workflow_id)
    if not workflow or not workflow.current_version:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")
    definition = WorkflowDefinition.model_validate(workflow.current_version.definition)
    report = validate_workflow(definition)

    if workflow.status.value == "active":
        trigger_types = {
            node.type for node in definition.nodes
            if node.type in {"incoming_call", "incoming_sms", "ussd_request"}
        }
        conflicts = await service.find_conflicting_active_workflows(workflow, trigger_types)
        seen: set[tuple[int, str]] = set()
        for other, trigger_type in conflicts:
            key = (other.id, trigger_type)
            if key in seen:
                continue
            seen.add(key)
            report.issues.append(
                ValidationIssue(
                    level="warning",
                    message=(
                        f"'{other.name}' is also active with the same trigger ({trigger_type}); "
                        "only the most recently updated workflow will actually run for it"
                    ),
                )
            )
    return report


@router.post("/{workflow_id}/test-run", response_model=WorkflowRunOut)
async def test_run(workflow_id: int, data: TestRunRequest, service: ServiceDep) -> WorkflowRunOut:
    """Simulate a trigger so the workflow can be tested from the builder."""
    workflow = await service.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")

    payload = dict(data.payload)
    trigger_type = payload.pop("trigger_type", "") or _detect_trigger(workflow.current_version.definition)
    if not trigger_type:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Workflow has no trigger node to test")

    run = await service.test_run(workflow, trigger_type, payload)
    run = await service.reload_run(run)
    return WorkflowRunOut.model_validate(run, from_attributes=True)


def _detect_trigger(definition: dict) -> str:
    for node in definition.get("nodes", []):
        if node.get("type") in {"incoming_call", "incoming_sms", "ussd_request"}:
            return node["type"]
    return ""


@router.get("/{workflow_id}/runs", response_model=list[WorkflowRunOut])
async def list_runs(workflow_id: int, service: ServiceDep) -> list[WorkflowRunOut]:
    runs = await service.list_runs(workflow_id=workflow_id)
    return [WorkflowRunOut.model_validate(r, from_attributes=True) for r in runs]
