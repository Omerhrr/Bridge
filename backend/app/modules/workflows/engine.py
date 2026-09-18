"""Workflow execution engine (spec §13, §23).

The engine walks the graph node-by-node starting from the trigger:

    Workflow -> Run -> Node execution -> next node -> ... -> End

It owns routing, persistence of runs/events, and pausing/resuming when a node
needs user input (e.g. Collect Speech during a live call). Node behaviour and
provider access live in the node executors and service abstractions.
"""

import time
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.logging import log_event
from app.modules.ai.service import get_ai_service
from app.modules.communications.service import get_communication_service
from app.modules.workflows.models import Workflow, WorkflowEvent, WorkflowRun, WorkflowVersion
from app.modules.workflows.nodes.base import NodeResult, RunContext, ServiceBag
from app.modules.workflows.registry import get_spec
from app.modules.workflows.schemas import WorkflowDefinition


class NodeExecutionError(Exception):
    """Raised when a node reports failure — stops the run (spec §34)."""


class WorkflowEngine:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ runs
    def start_run(
        self,
        workflow: Workflow,
        variables: dict | None = None,
        conversation_id: int | None = None,
    ) -> WorkflowRun:
        version = (
            self.db.query(WorkflowVersion)
            .filter(WorkflowVersion.workflow_id == workflow.id)
            .order_by(WorkflowVersion.version_number.desc())
            .first()
        )
        if version is None:
            raise ValueError(f"Workflow {workflow.name!r} has no stored version")

        run = WorkflowRun(
            id=f"run_{uuid.uuid4().hex[:10]}",
            workflow_id=workflow.id,
            version_id=version.id,
            conversation_id=conversation_id,
            status="running",
            variables=dict(variables or {}),
        )
        self.db.add(run)
        self.db.commit()
        log_event("workflow.started", workflow_run_id=run.id, conversation_id=conversation_id)
        return run

    def resume(self, run: WorkflowRun, input_variables: dict | None = None) -> WorkflowRun:
        """Continue a paused run from its current node with fresh input."""
        if input_variables:
            run.variables.update(input_variables)
        self.db.commit()
        return self._execute(run)

    # ------------------------------------------------------------- execution
    def _definition(self, run: WorkflowRun) -> WorkflowDefinition:
        return WorkflowDefinition.model_validate(run.version.definition)

    def _edge_from(self, definition: WorkflowDefinition, node_id: str, branch: str | None) -> str | None:
        """Return the next node id, honouring branch handles when present."""
        candidates = [e for e in definition.edges if e.source == node_id]
        if not candidates:
            return None
        if branch is not None and len(candidates) > 1:
            matching = [e for e in candidates if (e.source_handle or "out") == branch]
            if matching:
                return matching[0].target
            unlabelled = [e for e in candidates if not e.source_handle]
            if unlabelled:
                return unlabelled[0].target
            return None
        return candidates[0].target

    def _execute(self, run: WorkflowRun) -> WorkflowRun:
        started = time.perf_counter()
        definition = self._definition(run)
        services = ServiceBag(ai=get_ai_service(), comms=get_communication_service())
        ctx = RunContext(run_id=run.id, variables=dict(run.variables))

        # A resuming run restarts from its paused node; a fresh run starts at the trigger.
        resuming = run.status == "waiting_input" and run.current_node is not None
        node_id = run.current_node if resuming else self._entry_node(definition)
        skip_current = resuming  # the paused node already produced its prompt; input arrived
        run.status = "running"

        try:
            while node_id:
                node = next((n for n in definition.nodes if n.id == node_id), None)
                if node is None:
                    raise ValueError(f"Node {node_id!r} referenced by edges does not exist in definition")

                spec = get_spec(node.type)
                actions_before = len(ctx.actions)
                if skip_current:
                    result = NodeResult(status="completed", detail={"resumed": True})
                    result.branch = None
                else:
                    result = spec.executor(node.config or {}, ctx, services)
                actions_delta = ctx.actions[actions_before:]
                skip = skip_current
                skip_current = False

                if not skip:
                    self._record_event(run, node, result, actions_delta)

                if result.output:
                    run.variables.update(result.output)
                    ctx.variables.update(result.output)  # downstream nodes see it immediately
                run.current_node = node_id

                if result.status == "failed":
                    raise NodeExecutionError(
                        (result.detail or {}).get("error") or f"Node {node.type} failed"
                    )

                if result.waiting:
                    run.status = "waiting_input"
                    run.variables.update(ctx.variables)
                    self.db.commit()
                    log_event("workflow.waiting_input", workflow_run_id=run.id, node_id=node.id)
                    return run

                next_id = self._edge_from(definition, node.id, result.branch)
                if next_id is None:
                    break  # no outgoing edge -> implicit end
                next_node = next((n for n in definition.nodes if n.id == next_id), None)
                if next_node is None:
                    raise ValueError(f"Node {next_id!r} referenced by edges does not exist in definition")
                if next_node.type == "end":
                    self._record_event(run, next_node, NodeResult(detail={"ended": True}), [])
                    node_id = None
                    break
                node_id = next_id

            run.status = "completed"
            run.current_node = None
            run.finished_at = datetime.now(UTC).replace(tzinfo=None)
            run.duration_ms = round((time.perf_counter() - started) * 1000, 1)
            run.variables.update(ctx.variables)
            log_event("workflow.completed", workflow_run_id=run.id, conversation_id=run.conversation_id)
        except Exception as exc:  # noqa: BLE001 — controlled failure behaviour (spec §34)
            run.status = "failed"
            run.error = f"{type(exc).__name__}: {exc}"
            run.finished_at = datetime.now(UTC).replace(tzinfo=None)
            run.duration_ms = round((time.perf_counter() - started) * 1000, 1)
            log_event("workflow.failed", level=40, workflow_run_id=run.id, detail=str(exc))
        self.db.commit()
        return run

    def _entry_node(self, definition: WorkflowDefinition) -> str:
        trigger_types = {"incoming_call", "incoming_sms", "ussd_request", "start"}
        for node in definition.nodes:
            if node.type in trigger_types:
                return node.id
        if definition.nodes:
            return definition.nodes[0].id
        raise ValueError("Workflow definition has no nodes")

    def _record_event(self, run: WorkflowRun, node, result: NodeResult, actions: list[dict]) -> None:
        detail = dict(result.detail or {})
        if actions:
            detail["actions"] = actions
        self.db.add(
            WorkflowEvent(
                run_id=run.id,
                node_id=node.id,
                node_type=node.type,
                node_label=get_spec(node.type).label,
                status=result.status,
                detail=detail,
            )
        )
        self.db.commit()


def get_engine(db: Session) -> WorkflowEngine:
    return WorkflowEngine(db)
