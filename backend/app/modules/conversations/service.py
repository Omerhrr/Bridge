"""Conversation service: listing and timeline construction (spec sections 27-28)."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.conversations.models import Conversation
from app.modules.conversations.schemas import TimelineEvent
from app.modules.workflows.models import WorkflowRun

_EVENT_LABELS = {
    "call.received": "Incoming call",
    "call.started": "Call started",
    "call.completed": "Call completed",
    "call.played_voice": "Audio played",
    "call.play_audio": "Playing audio",
    "call.play_text": "Playing text",
    "sms.received": "Incoming SMS",
    "sms.sent": "SMS sent",
    "ussd.received": "USSD session started",
    "speech.transcription.completed": "Transcript generated",
    "translation.completed": "Translation completed",
    "tts.generated": "Audio generated",
    "node.started": "Step started",
    "node.completed": "Step completed",
    "workflow.started": "Workflow started",
    "workflow.completed": "Workflow completed",
    "workflow.failed": "Workflow failed",
    "condition.evaluated": "Condition evaluated",
}


class ConversationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_conversations(self, limit: int = 100) -> list[Conversation]:
        result = await self.session.execute(
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .order_by(Conversation.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_conversation(self, conversation_id: int) -> Conversation | None:
        result = await self.session.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.messages))
        )
        return result.scalar_one_or_none()

    async def build_timeline(self, conversation: Conversation) -> list[TimelineEvent]:
        """Merge conversation messages with workflow run events chronologically."""
        events: list[TimelineEvent] = []

        for message in conversation.messages:
            events.append(
                TimelineEvent(
                    timestamp=message.created_at,
                    kind="message",
                    label=f"{'Caller' if message.role == 'caller' else 'Bridge'} ({message.channel})",
                    detail={
                        "content": message.content,
                        "translated": message.translated_content,
                        "source_language": message.source_language,
                        "target_language": message.target_language,
                    },
                )
            )

        if conversation.workflow_run_id:
            result = await self.session.execute(
                select(WorkflowRun).where(WorkflowRun.id == conversation.workflow_run_id)
            )
            run = result.scalar_one_or_none()
            if run:
                from app.modules.workflows.models import WorkflowEvent

                run_events = await self.session.execute(
                    select(WorkflowEvent)
                    .where(WorkflowEvent.run_id == run.id)
                    .order_by(WorkflowEvent.created_at)
                )
                for run_event in run_events.scalars():
                    label = _EVENT_LABELS.get(run_event.event, run_event.event.replace(".", " ").title())
                    if run_event.event in {"node.started", "node.completed", "workflow.started"}:
                        continue  # keep the timeline readable
                    events.append(
                        TimelineEvent(
                            timestamp=run_event.created_at,
                            kind="event",
                            label=label,
                            detail=run_event.payload or {},
                        )
                    )

        events.sort(key=lambda e: e.timestamp)
        return events
