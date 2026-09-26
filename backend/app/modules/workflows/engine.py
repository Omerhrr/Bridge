"""Workflow execution engine (spec sections 13/56).

    Telecom Event -> Workflow Run -> Node -> Node -> ... -> End

The engine walks the definition graph starting from the trigger node that
matches the incoming event, executing nodes and following edges. Execution
history is recorded per node so the UI can trace exactly what happened.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger, log_event, new_correlation_id
from app.modules.ai.service import AIService
from app.modules.communications.service import CommunicationService
from app.modules.conversations.models import Conversation, ConversationMessage
from app.modules.workflows.models import (
    RunStatus,
    WorkflowEvent,
    WorkflowRun,
    WorkflowVersion,
)
from app.modules.workflows.nodes.base import (
    BaseNode,
    NodeContext,
    NodeExecutionError,
    NodeResult,
)
from app.modules.workflows.registry import get_node_class
from app.modules.workflows.schemas import WorkflowDefinition

MAX_STEPS = 50

logger = get_logger("bridge.workflow.engine")


class WorkflowEngine:
    def __init__(self, session: AsyncSession, ai: AIService, comms: CommunicationService):
        self.session = session
        self.ai = ai
        self.comms = comms

    async def _record_event(
        self,
        run_id: str,
        event: str,
        node_id: str | None,
        node_type: str | None,
        payload: dict,
    ) -> None:
        self.session.add(
            WorkflowEvent(run_id=run_id, node_id=node_id, node_type=node_type,
                          event=event, payload=payload)
        )
        await self.session.flush()

    async def start_run(
        self,
        version: WorkflowVersion,
        trigger_type: str,
        trigger_payload: dict,
        conversation: Conversation | None = None,
        trigger_node_id: str | None = None,
    ) -> WorkflowRun:
        """Create a run for a workflow version and execute it synchronously."""
        definition = WorkflowDefinition.model_validate(version.definition)
        run = WorkflowRun(
            id=f"run_{uuid.uuid4().hex[:10]}",
            workflow_id=version.workflow_id,
            version_id=version.id,
            conversation_id=conversation.id if conversation else None,
            status=RunStatus.running,
            trigger_payload=trigger_payload,
            variables={"correlation_id": new_correlation_id()},
        )
        self.session.add(run)
        await self.session.flush()
        log_event(logger, "workflow.started", workflow_run_id=run.id, workflow_id=version.workflow_id)

        try:
            await self._execute(run, definition, trigger_type, trigger_payload, trigger_node_id)
        except NodeExecutionError as exc:
            run.status = RunStatus.failed
            run.error = str(exc)
            run.finished_at = datetime.now(timezone.utc)
            await self._record_event(run.id, "workflow.failed", None, None, {"error": str(exc)})
            log_event(logger, "workflow.failed", workflow_run_id=run.id, error=str(exc))
        except Exception as exc:  # unexpected engine failure
            run.status = RunStatus.failed
            run.error = f"engine error: {exc}"
            run.finished_at = datetime.now(timezone.utc)
            await self._record_event(run.id, "workflow.failed", None, None, {"error": str(exc)})
            logger.exception("workflow crashed", extra={"extra_fields": {"workflow_run_id": run.id}})
        return run

    async def _execute(
        self,
        run: WorkflowRun,
        definition: WorkflowDefinition,
        trigger_type: str,
        trigger_payload: dict,
        trigger_node_id: str | None,
    ) -> None:
        node_by_id = {node.id: node for node in definition.nodes}
        edges_by_source: dict[str, list] = {}
        for edge in definition.edges:
            edges_by_source.setdefault(edge.source, []).append(edge)

        # Find the starting node: explicit match, else trigger matching type.
        start = None
        if trigger_node_id and trigger_node_id in node_by_id:
            start = node_by_id[trigger_node_id]
        else:
            for node in definition.nodes:
                if node.type == trigger_type:
                    start = node
                    break
        if start is None:
            raise NodeExecutionError(f"No trigger node of type '{trigger_type}' in workflow")

        await self._run_nodes(run, definition, start, trigger_payload, node_by_id,
                              edges_by_source, resume_input=None)

    async def resume_run(self, run: WorkflowRun, trigger_payload: dict) -> WorkflowRun:
        """Continue a waiting run with fresh user input (e.g. a USSD session
        where the next callback carries the accumulated star input)."""
        version = await self.session.get(WorkflowVersion, run.version_id)
        if version is None:
            raise NodeExecutionError(f"Run '{run.id}' references a missing workflow version")
        definition = WorkflowDefinition.model_validate(version.definition)
        node_by_id = {node.id: node for node in definition.nodes}
        edges_by_source: dict[str, list] = {}
        for edge in definition.edges:
            edges_by_source.setdefault(edge.source, []).append(edge)

        start = node_by_id.get(run.current_node or "")
        if start is None:
            run.status = RunStatus.failed
            run.error = "Waiting node no longer exists in the workflow definition"
            run.finished_at = datetime.now(timezone.utc)
            await self._record_event(
                run.id, "workflow.failed", None, None, {"error": run.error}
            )
            return run

        # Fold the new input into the run variables (same fields the trigger
        # node sets on a fresh run).
        text = trigger_payload.get("text", "") or ""
        run.variables["ussd_input"] = text
        run.variables["ussd_selection"] = text.split("*")[-1] if text else ""
        run.trigger_payload = trigger_payload
        run.status = RunStatus.running
        log_event(logger, "workflow.resumed", workflow_run_id=run.id, selection=run.variables["ussd_selection"])

        try:
            await self._run_nodes(run, definition, start, trigger_payload, node_by_id,
                                  edges_by_source, resume_input={"text": text})
        except NodeExecutionError as exc:
            run.status = RunStatus.failed
            run.error = str(exc)
            run.finished_at = datetime.now(timezone.utc)
            await self._record_event(run.id, "workflow.failed", None, None, {"error": str(exc)})
        except Exception as exc:  # unexpected engine failure
            run.status = RunStatus.failed
            run.error = f"engine error: {exc}"
            run.finished_at = datetime.now(timezone.utc)
            await self._record_event(run.id, "workflow.failed", None, None, {"error": str(exc)})
        return run

    async def _run_nodes(
        self,
        run: WorkflowRun,
        definition: WorkflowDefinition,
        start,
        trigger_payload: dict,
        node_by_id: dict,
        edges_by_source: dict[str, list],
        resume_input: dict | None,
    ) -> None:
        async def record(event: str, node_id=None, node_type=None, payload: dict | None = None) -> None:
            await self._record_event(run.id, event, node_id, node_type, payload or {})

        ctx = NodeContext(
            run_id=run.id,
            variables=run.variables,
            services={
                "ai": self.ai,
                "comms": self.comms,
                "record_event": record,
            },
            trigger_payload=trigger_payload,
            resume_input=resume_input,
        )

        current = start
        steps = 0
        while current is not None and steps < MAX_STEPS:
            steps += 1
            node_class = get_node_class(current.type)
            run.current_node = current.id
            if node_class is None:
                raise NodeExecutionError(f"Unknown node type '{current.type}'")

            instance: BaseNode = node_class()
            await record("node.started", current.id, current.type)
            try:
                result: NodeResult = await instance.execute(current.config or {}, ctx)
            except NodeExecutionError:
                raise
            except Exception as exc:
                raise NodeExecutionError(f"{instance.label} failed: {exc}") from exc

            # Only the node the run resumed at consumes the resume input;
            # later menu nodes must wait for fresh input again.
            ctx.resume_input = None

            await record("node.completed", current.id, current.type)
            await self.session.flush()

            if result.wait_for_input:
                # Pause the run: a follow-up event (next USSD request with the
                # same session id) resumes execution from this node.
                run.status = RunStatus.waiting
                await record("run.waiting_for_input", current.id, current.type)
                log_event(logger, "workflow.waiting", workflow_run_id=run.id, node=current.id)
                return

            outgoing = edges_by_source.get(current.id, [])
            next_node = None
            if result.next_handle:
                for edge in outgoing:
                    if edge.source_handle == result.next_handle:
                        next_node = node_by_id.get(edge.target)
                        break
            elif outgoing:
                next_node = node_by_id.get(outgoing[0].target)

            if next_node is None and outgoing:
                # A handle was requested but no matching edge exists.
                await record("branch.terminated", current.id, current.type,
                             payload={"handle": result.next_handle or "default"})
            current = next_node

        if steps >= MAX_STEPS:
            raise NodeExecutionError("Workflow exceeded the maximum number of steps (possible infinite loop)")

        run.status = RunStatus.completed
        run.current_node = None
        run.finished_at = datetime.now(timezone.utc)
        await self._record_event(run.id, "workflow.completed", None, None, {"steps": steps})
        log_event(logger, "workflow.completed", workflow_run_id=run.id, steps=steps)

        # Close the conversation if this run belongs to one.
        if run.conversation_id:
            conversation = await self.session.get(Conversation, run.conversation_id)
            if conversation and conversation.status == "active":
                conversation.status = "completed"
                conversation.ended_at = datetime.now(timezone.utc)

    async def record_incoming_message(
        self, conversation: Conversation, role: str, channel: str,
        content: str, translated: str | None = None,
        source_language: str | None = None, target_language: str | None = None,
    ) -> ConversationMessage:
        message = ConversationMessage(
            conversation_id=conversation.id,
            role=role,
            channel=channel,
            content=content,
            translated_content=translated,
            source_language=source_language,
            target_language=target_language,
        )
        self.session.add(message)
        await self.session.flush()
        return message
