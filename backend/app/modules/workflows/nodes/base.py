"""Node executor protocol and shared helpers.

Every node executor has the signature::

    def execute(config: dict, ctx: RunContext, services: ServiceBag) -> NodeResult

The engine owns persistence and routing; nodes only compute.
"""

from dataclasses import dataclass, field
from typing import Any

import re

_TEMPLATE_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


@dataclass
class RunContext:
    """Mutable state of a single workflow run (spec §13)."""

    run_id: str
    variables: dict[str, Any] = field(default_factory=dict)
    # Actions meant for the telecom layer, e.g. {"action": "Say", "text": "..."}.
    actions: list[dict] = field(default_factory=list)
    branch: str | None = None  # chosen output handle (condition/switch)
    waiting_input: str | None = None  # set when the run pauses for user input


@dataclass
class NodeResult:
    status: str = "completed"  # completed | waiting
    output: dict[str, Any] = field(default_factory=dict)  # merged into run variables
    detail: dict[str, Any] = field(default_factory=dict)  # stored on the WorkflowEvent
    branch: str | None = None
    waiting: bool = False


@dataclass
class ServiceBag:
    """Lazy access to AI / communications services (kept provider-agnostic)."""

    ai: Any  # app.modules.ai.service.AIService
    comms: Any  # app.modules.communications.service.CommunicationService


def render_template(template: str, variables: dict[str, Any]) -> str:
    """Replace ``{{variable}}`` placeholders with run variables."""

    def _sub(match: re.Match) -> str:
        value = variables.get(match.group(1), "")
        return "" if value is None else str(value)

    return _TEMPLATE_RE.sub(_sub, template or "")


def resolve_value(config: dict, variables: dict[str, Any], value_key: str, var_key: str | None = None) -> Any:
    """Resolve a config value either literally or from a run variable.

    ``var_key`` is the *config key* whose value names a run variable
    (e.g. ``config={"from_variable": "transcript"}`` -> ``variables["transcript"]``).
    Priority: named run variable > templated literal value.
    """
    if var_key:
        variable_name = config.get(var_key)
        if variable_name and variables.get(variable_name) not in (None, ""):
            return variables[variable_name]
    raw = config.get(value_key)
    if isinstance(raw, str):
        return render_template(raw, variables)
    return raw


def completed(**kwargs: Any) -> NodeResult:
    return NodeResult(status="completed", **kwargs)


def execute_start(config: dict, ctx: RunContext, services: ServiceBag) -> NodeResult:
    """Start node — explicit entry point, passes everything through."""
    return completed()


def waiting(prompt: str, detail: dict | None = None) -> NodeResult:
    """Node pauses the run until the next webhook supplies input."""
    return NodeResult(status="waiting", waiting=True, detail=detail or {}, output={"last_prompt": prompt})
