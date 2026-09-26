"""Global run endpoints (spec section 29)."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import DbSession
from app.modules.workflows.schemas import WorkflowRunOut
from app.modules.workflows.service import WorkflowService

router = APIRouter(prefix="/runs", tags=["runs"])


async def get_service(db: DbSession) -> WorkflowService:
    from app.modules.workflows.engine import WorkflowEngine
    from app.modules.ai.service import get_ai_service
    from app.modules.communications.service import get_communication_service

    return WorkflowService(db, WorkflowEngine(db, get_ai_service(), await get_communication_service(db)))


ServiceDep = Annotated[WorkflowService, Depends(get_service)]


@router.get("", response_model=list[WorkflowRunOut])
async def list_runs(service: ServiceDep) -> list[WorkflowRunOut]:
    runs = await service.list_runs()
    return [WorkflowRunOut.model_validate(r, from_attributes=True) for r in runs]


@router.get("/{run_id}", response_model=WorkflowRunOut)
async def get_run(run_id: str, service: ServiceDep) -> WorkflowRunOut:
    run = await service.get_run(run_id)
    if not run:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    return WorkflowRunOut.model_validate(run, from_attributes=True)
