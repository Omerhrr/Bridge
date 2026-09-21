"""Node base classes for the workflow engine (spec sections 11-13).

Every node declares metadata used by both the validator and the frontend
palette (label, category, handles, config schema) and implements async
`execute` against a NodeContext.
"""
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import log_event, get_logger

logger = get_logger("bridge.workflow.node")


class NodeExecutionError(Exception):
    """Raised when a node fails during execution."""


def render_template(value: str, variables: dict[str, Any]) -> str:
    """Substitute {{variable}} placeholders in a node config string.

    Unknown variables render as an empty string, matching the forgiving
    behaviour of the rest of the engine.
    """
    import re

    if not isinstance(value, str):
        return value
    return re.sub(
        r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}",
        lambda match: str(variables.get(match.group(1), "")),
        value,
    )


@dataclass
class NodeContext:
    """Runtime context handed to each node execution."""

    run_id: str
    variables: dict[str, Any] = field(default_factory=dict)
    services: dict[str, Any] = field(default_factory=dict)
    trigger_payload: dict[str, Any] = field(default_factory=dict)
    # Set when the engine is resuming a paused run (e.g. a USSD menu that
    # waited for user input). Nodes use it to continue where they left off.
    resume_input: dict[str, Any] | None = None

    async def record(self, event: str, node: "BaseNode | None" = None, **payload) -> None:
        callback = self.services.get("record_event")
        if callback:
            await callback(
                event=event,
                node_id=getattr(node, "id", None),
                node_type=getattr(node, "type", None),
                payload=payload,
            )
        log_event(
            logger,
            event,
            workflow_run_id=self.run_id,
            node=getattr(node, "type", None),
            **payload,
        )


@dataclass
class NodeResult:
    outputs: dict[str, Any] = field(default_factory=dict)
    # Which outgoing handle to follow (used by condition/switch nodes).
    next_handle: str | None = None
    # When True the engine pauses the run (status=waiting) instead of
    # continuing, e.g. a USSD menu displayed and waiting for user input.
    wait_for_input: bool = False


class BaseNode:
    """Base class for all workflow nodes."""

    type: str = ""
    label: str = ""
    category: str = "flow"  # trigger | voice | ai | messaging | logic | flow
    description: str = ""
    icon: str = "circle"
    inputs: list[str] = ["in"]
    outputs: list[str] = ["out"]
    config_schema: list[dict[str, Any]] = []

    async def execute(self, config: dict[str, Any], ctx: NodeContext) -> NodeResult:
        raise NotImplementedError

    def missing_required_config(self, config: dict[str, Any]) -> list[str]:
        """Return names of required config fields that are missing."""
        missing = []
        for spec in self.config_schema:
            if spec.get("required") and not str(config.get(spec["name"], "") or "").strip():
                missing.append(spec["name"])
        return missing

    def metadata(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "label": self.label,
            "category": self.category,
            "description": self.description,
            "icon": self.icon,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "config_schema": self.config_schema,
        }
