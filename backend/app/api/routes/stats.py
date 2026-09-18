"""Dashboard stats — is Bridge working? (spec §19)"""

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.conversations.models import Conversation
from app.modules.workflows.models import Workflow, WorkflowRun

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
def stats(db: Session = Depends(get_db)):
    total_runs = db.query(func.count(WorkflowRun.id)).scalar() or 0
    completed = db.query(func.count(WorkflowRun.id)).filter(WorkflowRun.status == "completed").scalar() or 0
    failed = db.query(func.count(WorkflowRun.id)).filter(WorkflowRun.status == "failed").scalar() or 0
    voice_calls = (
        db.query(func.count(Conversation.id)).filter(Conversation.channel == "voice").scalar() or 0
    )
    sms_count = (
        db.query(func.count(Conversation.id)).filter(Conversation.channel == "sms").scalar() or 0
    )
    active_workflows = db.query(func.count(Workflow.id)).filter(Workflow.enabled.is_(True)).scalar() or 0
    total_workflows = db.query(func.count(Workflow.id)).scalar() or 0
    success_rate = round((completed / total_runs) * 100, 1) if total_runs else None

    recent = (
        db.query(Conversation)
        .order_by(Conversation.started_at.desc())
        .limit(6)
        .all()
    )

    # Workflow activity: runs + success % per workflow (spec §19 bottom panel).
    activity_rows = (
        db.query(
            Workflow.id,
            Workflow.name,
            func.count(WorkflowRun.id),
            func.sum(case((WorkflowRun.status == "completed", 1), else_=0)),
        )
        .outerjoin(WorkflowRun, WorkflowRun.workflow_id == Workflow.id)
        .group_by(Workflow.id, Workflow.name)
        .all()
    )
    activity = [
        {
            "workflow_id": workflow_id,
            "name": name,
            "runs": int(runs or 0),
            "success_rate": round((int(done or 0) / runs) * 100, 1) if runs else None,
        }
        for workflow_id, name, runs, done in activity_rows
    ]

    return {
        "calls": voice_calls,
        "sms": sms_count,
        "active_workflows": active_workflows,
        "total_workflows": total_workflows,
        "total_runs": total_runs,
        "completed_runs": completed,
        "failed_runs": failed,
        "success_rate": success_rate,
        "recent_conversations": [
            {
                "id": c.id,
                "channel": c.channel,
                "from_number": c.from_number,
                "language": c.language,
                "target_language": c.target_language,
                "status": c.status,
                "started_at": c.started_at.isoformat() if c.started_at else None,
            }
            for c in recent
        ],
        "workflow_activity": activity,
    }
