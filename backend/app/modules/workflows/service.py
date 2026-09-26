"""Workflow service: persistence, versioning and trigger dispatch (spec sections 12/31)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.conversations.models import Conversation
from app.modules.workflows.engine import WorkflowEngine
from app.modules.workflows.models import (
    RunStatus,
    Workflow,
    WorkflowRun,
    WorkflowStatus,
    WorkflowVersion,
)

from app.modules.workflows.schemas import WorkflowCreate, WorkflowDefinition, WorkflowUpdate


class WorkflowService:
    def __init__(self, session: AsyncSession, engine: WorkflowEngine):
        self.session = session
        self.engine = engine

    async def list_workflows(self) -> list[Workflow]:
        result = await self.session.execute(
            select(Workflow)
            .options(selectinload(Workflow.current_version), selectinload(Workflow.versions))
            .order_by(Workflow.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_workflow(self, workflow_id: int, fresh: bool = False) -> Workflow | None:
        query = (
            select(Workflow)
            .where(Workflow.id == workflow_id)
            .options(
                selectinload(Workflow.current_version),
                selectinload(Workflow.versions),
                selectinload(Workflow.runs),
            )
        )
        if fresh:
            # Bypass the session identity map so mutations made in this
            # request (e.g. a new version) are reflected in the response.
            query = query.execution_options(populate_existing=True)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_workflow(self, data: WorkflowCreate) -> Workflow:
        workflow = Workflow(name=data.name, description=data.description)
        self.session.add(workflow)
        await self.session.flush()

        definition = data.definition or WorkflowDefinition()
        version = WorkflowVersion(
            workflow_id=workflow.id, version_number=1,
            definition=definition.model_dump(), comment="initial",
        )
        self.session.add(version)
        await self.session.flush()
        workflow.current_version_id = version.id
        await self.session.flush()
        return workflow

    async def delete_workflow(self, workflow_id: int) -> bool:
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            return False
        # Delete dependent rows first (no ORM cascade configured for runs).
        from app.modules.workflows.models import WorkflowEvent

        await self.session.execute(delete(WorkflowEvent).where(WorkflowEvent.run_id.in_(
            select(WorkflowRun.id).where(WorkflowRun.workflow_id == workflow_id)
        )))
        await self.session.execute(delete(WorkflowRun).where(WorkflowRun.workflow_id == workflow_id))
        await self.session.execute(delete(WorkflowVersion).where(WorkflowVersion.workflow_id == workflow_id))
        await self.session.delete(workflow)
        await self.session.flush()
        return True

    async def update_workflow(self, workflow: Workflow, data: WorkflowUpdate) -> Workflow:
        if data.name is not None:
            workflow.name = data.name
        if data.description is not None:
            workflow.description = data.description
        if data.status is not None:
            workflow.status = WorkflowStatus(data.status)
        workflow.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return workflow

    async def save_version(self, workflow: Workflow, definition: WorkflowDefinition, comment: str = "") -> WorkflowVersion:
        version_number = (
            max((v.version_number for v in workflow.versions), default=0) + 1
        )
        version = WorkflowVersion(
            workflow_id=workflow.id,
            version_number=version_number,
            definition=definition.model_dump(),
            comment=comment,
        )
        self.session.add(version)
        await self.session.flush()
        workflow.current_version_id = version.id
        workflow.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return version

    async def find_active_workflow_for_trigger(self, trigger_type: str, called_number: str | None = None) -> Workflow | None:
        """Find an active workflow whose trigger matches an incoming event.

        More than one active workflow can declare the same trigger type (a
        user testing a new SMS flow while an older one is still active, for
        example). Without an explicit order, which one answers is whatever
        order the database happens to return, so the same event could be
        routed differently between requests. Preferring the most recently
        updated workflow makes "the one I just activated" the one that
        actually wins, which matches what a person editing workflows expects.
        """
        result = await self.session.execute(
            select(Workflow)
            .where(Workflow.status == WorkflowStatus.active)
            .options(selectinload(Workflow.current_version))
            .order_by(Workflow.updated_at.desc())
        )
        candidates = result.scalars().all()
        for workflow in candidates:
            version = workflow.current_version
            if not version:
                continue
            nodes = version.definition.get("nodes", [])
            for node in nodes:
                if node.get("type") != trigger_type:
                    continue
                configured = (node.get("config") or {}).get("phone_number")
                # A trigger without a configured number matches any incoming event;
                # with a number configured it must match exactly.
                if not configured or (called_number and str(called_number).endswith(str(configured))):
                    return workflow
        return None

    async def dispatch_telecom_event(
        self,
        trigger_type: str,
        payload: dict,
        channel: str,
        a_number: str | None,
        b_number: str | None,
        idempotency_key: str | None = None,
    ) -> WorkflowRun | None:
        """Entry point for webhooks: find workflow, create conversation, execute."""
        from app.modules.communications.models import SmsMessage
        from app.core.logging import log_event, get_logger

        logger = get_logger("bridge.workflow.service")

        # Idempotency (spec section 45): skip events we already processed.
        if idempotency_key and channel == "sms":
            existing = await self.session.execute(
                select(SmsMessage).where(SmsMessage.provider_message_id == idempotency_key)
            )
            if existing.scalar_one_or_none():
                log_event(logger, "webhook.duplicate_ignored", provider_message_id=idempotency_key)
                return None

        # USSD sessions: a waiting run means the user is mid-menu; the next
        # callback for the same session resumes that run instead of starting
        # a new one (spec section 13, interactive sessions).
        if channel == "ussd":
            waiting_run = await self._find_waiting_ussd_run(payload.get("session_id", ""))
            if waiting_run:
                return await self.engine.resume_run(waiting_run, payload)

        workflow = await self.find_active_workflow_for_trigger(trigger_type, payload.get("called"))
        if workflow is None or not workflow.current_version:
            log_event(logger, "trigger.unmatched", trigger_type=trigger_type)
            return None

        conversation = Conversation(
            channel=channel,
            status="active",
            a_number=a_number,
            b_number=b_number,
            workflow_run_id=None,
        )
        self.session.add(conversation)
        await self.session.flush()

        # Persist the inbound message so duplicate webhook deliveries
        # (idempotency, spec section 45) can be detected.
        if channel == "sms":
            self.session.add(
                SmsMessage(
                    provider_message_id=idempotency_key,
                    conversation_id=conversation.id,
                    direction="inbound",
                    from_number=a_number,
                    to_number=b_number,
                    text=payload.get("text", ""),
                    status="received",
                )
            )
            await self.session.flush()

        run = await self.engine.start_run(
            version=workflow.current_version,
            trigger_type=trigger_type,
            trigger_payload=payload,
            conversation=conversation,
        )
        conversation.workflow_run_id = run.id

        # Record the incoming message inside the conversation timeline.
        text = payload.get("text", "")
        if channel in ("sms", "whatsapp") and text:
            await self.engine.record_incoming_message(
                conversation, role="caller", channel=channel, content=text
            )
        return run

    async def find_conflicting_active_workflows(
        self, workflow: Workflow, trigger_types: set[str],
    ) -> list[tuple[Workflow, str]]:
        """Other active workflows that would race this one for the same event.

        Only one workflow can ever answer a given trigger type (see
        ``find_active_workflow_for_trigger``), so activating a second one
        with an overlapping trigger silently shadows whichever loses the
        "most recently updated" tie-break — a mistake worth surfacing during
        validation rather than letting someone find out from a customer's
        message going to the wrong flow.
        """
        if not trigger_types:
            return []
        result = await self.session.execute(
            select(Workflow)
            .where(Workflow.status == WorkflowStatus.active, Workflow.id != workflow.id)
            .options(selectinload(Workflow.current_version))
        )
        conflicts: list[tuple[Workflow, str]] = []
        for other in result.scalars().all():
            if not other.current_version:
                continue
            other_types = {
                node.get("type") for node in other.current_version.definition.get("nodes", [])
            }
            for shared in trigger_types & other_types:
                conflicts.append((other, shared))
        return conflicts

    async def _find_waiting_ussd_run(self, session_id: str) -> WorkflowRun | None:
        """Locate a paused USSD run for an ongoing telecom session."""
        if not session_id:
            return None
        result = await self.session.execute(
            select(WorkflowRun)
            .where(WorkflowRun.status == RunStatus.waiting)
            .order_by(WorkflowRun.started_at.desc())
            .limit(20)
        )
        for run in result.scalars().all():
            payload = run.trigger_payload or {}
            if payload.get("session_id") == session_id:
                return run
        return None

    async def sms_event_seen(self, provider_message_id: str) -> bool:
        """True when an inbound SMS with this provider id was already stored.

        Used by the webhook to report duplicates accurately after the
        dispatcher skipped the event (spec section 45).
        """
        from app.modules.communications.models import SmsMessage
        from app.modules.messaging.models import MessageLog

        existing = await self.session.execute(
            select(SmsMessage.id).where(SmsMessage.provider_message_id == provider_message_id).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            return True
        logged = await self.session.execute(
            select(MessageLog.id).where(
                MessageLog.direction == "inbound",
                MessageLog.provider_message_id == provider_message_id,
            ).limit(1)
        )
        return logged.scalar_one_or_none() is not None

    async def test_run(self, workflow: Workflow, trigger_type: str, payload: dict) -> WorkflowRun:
        """Simulated run from the Test button (spec section 20)."""
        if not workflow.current_version:
            definition = WorkflowDefinition()
            await self.save_version(workflow, definition, "empty test version")
        return await self.engine.start_run(
            version=workflow.current_version,
            trigger_type=trigger_type,
            trigger_payload=payload,
            trigger_node_id=None,
        )

    async def list_runs(self, workflow_id: int | None = None, limit: int = 50) -> list[WorkflowRun]:
        query = (
            select(WorkflowRun)
            .options(selectinload(WorkflowRun.events))
            .order_by(WorkflowRun.started_at.desc())
            .limit(limit)
        )
        if workflow_id:
            query = query.where(WorkflowRun.workflow_id == workflow_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_run(self, run_id: str) -> WorkflowRun | None:
        result = await self.session.execute(
            select(WorkflowRun)
            .where(WorkflowRun.id == run_id)
            .options(selectinload(WorkflowRun.events))
        )
        return result.scalar_one_or_none()

    async def reload_run(self, run: WorkflowRun) -> WorkflowRun:
        """Re-fetch a run with events eager-loaded for serialization."""
        reloaded = await self.get_run(run.id)
        return reloaded or run
