"""Dashboard summary endpoint (spec section 19).

Answers four questions: is Bridge working, how many communication sessions
happened, which workflows are active, and are there any failures.
"""
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.dependencies import DbSession
from app.core.config import settings
from app.modules.communications.models import Call, SmsMessage
from app.modules.conversations.models import Conversation
from app.modules.workflows.models import Workflow, WorkflowRun

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardSummary(BaseModel):
    status: str
    calls: int
    sms: int
    active_workflows: int
    total_workflows: int
    success_rate: float
    recent_conversations: list[dict[str, Any]]
    workflow_activity: list[dict[str, Any]]


@router.get("/summary", response_model=DashboardSummary)
async def summary(db: DbSession) -> DashboardSummary:
    calls = (await db.execute(select(func.count()).select_from(Call))).scalar_one()
    sms = (await db.execute(select(func.count()).select_from(SmsMessage))).scalar_one()
    total_workflows = (await db.execute(select(func.count()).select_from(Workflow))).scalar_one()
    active_workflows = (
        await db.execute(select(func.count()).select_from(Workflow).where(Workflow.status == "active"))
    ).scalar_one()

    total_runs = (await db.execute(select(func.count()).select_from(WorkflowRun))).scalar_one()
    completed_runs = (
        await db.execute(select(func.count()).select_from(WorkflowRun).where(WorkflowRun.status == "completed"))
    ).scalar_one()
    success_rate = round(100.0 * completed_runs / total_runs, 1) if total_runs else 0.0

    recent = (
        await db.execute(
            select(Conversation).order_by(Conversation.started_at.desc()).limit(6)
        )
    ).scalars().all()

    workflows = (
        await db.execute(select(Workflow).order_by(Workflow.updated_at.desc()).limit(6))
    ).scalars().all()

    activity = []
    for workflow in workflows:
        runs = (
            await db.execute(
                select(func.count()).select_from(WorkflowRun).where(WorkflowRun.workflow_id == workflow.id)
            )
        ).scalar_one()
        ok = (
            await db.execute(
                select(func.count()).select_from(WorkflowRun).where(
                    WorkflowRun.workflow_id == workflow.id, WorkflowRun.status == "completed"
                )
            )
        ).scalar_one()
        activity.append(
            {
                "id": workflow.id,
                "name": workflow.name,
                "status": workflow.status.value,
                "runs": runs,
                "success_rate": round(100.0 * ok / runs, 1) if runs else 0.0,
            }
        )

    return DashboardSummary(
        status="ok",
        calls=calls,
        sms=sms,
        active_workflows=active_workflows,
        total_workflows=total_workflows,
        success_rate=success_rate,
        recent_conversations=[
            {
                "id": c.id,
                "channel": c.channel,
                "a_number": c.a_number,
                "b_number": c.b_number,
                "source_language": c.source_language,
                "target_language": c.target_language,
                "status": c.status,
                "started_at": c.started_at.isoformat(),
            }
            for c in recent
        ],
        workflow_activity=activity,
    )
