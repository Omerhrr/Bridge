"""Workflow CRUD, versioning, validation and deployment endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import require_api_token
from app.core.database import get_db
from app.modules.workflows import service
from app.modules.workflows.schemas import (
    ValidationReport,
    WorkflowCreate,
    WorkflowDefinition,
    WorkflowOut,
    WorkflowUpdate,
)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


def _to_out(workflow) -> WorkflowOut:
    return WorkflowOut(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        enabled=workflow.enabled,
        current_version=workflow.current_version,
        definition=WorkflowDefinition.model_validate(service.latest_definition(workflow)),
        created_at=workflow.created_at.isoformat() if workflow.created_at else None,
        updated_at=workflow.updated_at.isoformat() if workflow.updated_at else None,
    )


@router.get("", response_model=list[WorkflowOut])
def list_workflows(db: Session = Depends(get_db)):
    return [_to_out(w) for w in service.list_workflows(db)]


@router.post("", response_model=WorkflowOut, status_code=201, dependencies=[Depends(require_api_token)])
def create_workflow(payload: WorkflowCreate, db: Session = Depends(get_db)):
    if service.get_workflow_by_name(db, payload.name):
        raise HTTPException(status_code=409, detail="A workflow with this name already exists")
    return _to_out(service.create_workflow(db, payload))


@router.get("/{workflow_id}", response_model=WorkflowOut)
def get_workflow(workflow_id: int, db: Session = Depends(get_db)):
    workflow = service.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _to_out(workflow)


@router.put("/{workflow_id}", response_model=WorkflowOut, dependencies=[Depends(require_api_token)])
def update_workflow(workflow_id: int, payload: WorkflowUpdate, db: Session = Depends(get_db)):
    workflow = service.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _to_out(service.update_workflow(db, workflow, payload))


@router.delete("/{workflow_id}", status_code=204, dependencies=[Depends(require_api_token)])
def delete_workflow(workflow_id: int, db: Session = Depends(get_db)):
    workflow = service.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    service.delete_workflow(db, workflow)


@router.post("/{workflow_id}/validate", response_model=ValidationReport)
def validate_workflow(workflow_id: int, db: Session = Depends(get_db)):
    workflow = service.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return service.validate_definition(WorkflowDefinition.model_validate(service.latest_definition(workflow)))


@router.post("/validate", response_model=ValidationReport)
def validate_definition(payload: WorkflowDefinition, db: Session = Depends(get_db)):
    """Validate an unsaved definition straight from the builder."""
    return service.validate_definition(payload)


@router.post("/{workflow_id}/deploy", response_model=WorkflowOut, dependencies=[Depends(require_api_token)])
def deploy_workflow(workflow_id: int, definition: WorkflowDefinition, db: Session = Depends(get_db)):
    """Validate, store a new version and enable the workflow (spec §23)."""
    report = service.validate_definition(definition)
    if not report.valid:
        raise HTTPException(status_code=422, detail={"message": "Workflow validation failed", "report": report.model_dump()})
    workflow = service.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    service.update_workflow(db, workflow, WorkflowUpdate(definition=definition, enabled=True))
    return _to_out(workflow)
