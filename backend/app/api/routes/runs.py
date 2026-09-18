"""Workflow run endpoints — execution history and traces (spec §29)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.workflows.engine import get_engine
from app.modules.workflows.models import WorkflowEvent, WorkflowRun


router = APIRouter(prefix="/api/runs", tags=["runs"])


def _run_out(run: WorkflowRun) -> dict:
    return {
        "id": run.id,
        "workflow_id": run.workflow_id,
        "workflow_name": run.workflow.name if run.workflow else None,
        "version": run.version.version_number if run.version else None,
        "conversation_id": run.conversation_id,
        "status": run.status,
        "current_node": run.current_node,
        "variables": run.variables,
        "error": run.error,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "duration_ms": run.duration_ms,
        "events": [
            {
                "id": e.id,
                "node_id": e.node_id,
                "node_type": e.node_type,
                "node_label": e.node_label,
                "status": e.status,
                "detail": e.detail,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in run.events
        ],
    }


@router.get("")
def list_runs(db: Session = Depends(get_db), limit: int = 50, status: str | None = None):
    query = db.query(WorkflowRun).order_by(WorkflowRun.started_at.desc())
    if status:
        query = query.filter(WorkflowRun.status == status)
    return [_run_out(r) for r in query.limit(limit).all()]


@router.get("/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = db.get(WorkflowRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_out(run)


@router.post("/{run_id}/resume")
def resume_run(run_id: str, payload: dict, db: Session = Depends(get_db)):
    """Manually resume a paused run (used by the runs page for debugging)."""
    run = db.get(WorkflowRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    engine = get_engine(db)
    return _run_out(engine.resume(run, payload.get("variables")))
