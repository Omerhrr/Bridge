"""Logic node executors: condition, switch, delay, set_variable."""

import time

from app.modules.workflows.nodes.base import (
    RunContext,
    NodeResult,
    ServiceBag,
    completed,
    render_template,
)


def _get_variable(ctx: RunContext, name: str):
    return ctx.variables.get(name)


def execute_condition(config: dict, ctx: RunContext, services: ServiceBag) -> NodeResult:
    name = config.get("variable", "")
    operator = config.get("operator", "exists")
    expected = config.get("value")
    value = _get_variable(ctx, name)

    passed = False
    if operator == "exists":
        passed = value is not None
    elif operator == "not_empty":
        passed = value not in (None, "", [])
    elif operator == "equals":
        passed = str(value) == str(expected)
    elif operator == "contains":
        passed = str(expected).lower() in str(value or "").lower()

    return completed(branch="true" if passed else "false", detail={"condition": {name: value}, "result": passed})


def execute_switch(config: dict, ctx: RunContext, services: ServiceBag) -> NodeResult:
    name = config.get("variable", "")
    value = str(_get_variable(ctx, name) or "")
    cases = [case.strip() for case in (config.get("cases") or "").split(",") if case.strip()]
    branch = value if value in cases else "default"
    return completed(branch=branch, detail={"switch": {name: value}, "matched": branch})


def execute_delay(config: dict, ctx: RunContext, services: ServiceBag) -> NodeResult:
    seconds = min(float(config.get("seconds", 1) or 1), 10.0)
    time.sleep(seconds)
    return completed(detail={"delayed_seconds": seconds})


def execute_set_variable(config: dict, ctx: RunContext, services: ServiceBag) -> NodeResult:
    name = config.get("name", "")
    if not name:
        return NodeResult(status="failed", detail={"error": "set_variable: missing variable name"})
    raw = config.get("value")
    value = render_template(raw, ctx.variables) if isinstance(raw, str) else raw
    return completed(output={name: value, "last_node_output": value}, detail={name: value})
