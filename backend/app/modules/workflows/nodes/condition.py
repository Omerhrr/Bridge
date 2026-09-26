"""Logic nodes (spec section 11): condition, switch, delay, set variable."""
from typing import Any

import asyncio

from app.modules.workflows.nodes.base import BaseNode, NodeResult, render_template


class ConditionNode(BaseNode):
    type = "condition"
    label = "Condition"
    category = "logic"
    description = "Branches based on a variable comparison"
    icon = "git-branch"
    outputs = ["true", "false"]
    config_schema = [
        {"name": "variable", "label": "Variable", "type": "text", "required": True},
        {"name": "operator", "label": "Operator", "type": "select", "required": True,
         "options": ["equals", "not_equals", "contains", "is_empty", "not_empty"],
         "default": "not_empty"},
        {"name": "value", "label": "Value", "type": "text", "required": False,
         "hint": "Supports {{variables}} for comparing against another variable"},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        actual = ctx.variables.get(config.get("variable", ""), "")
        operator = config.get("operator", "not_empty")
        value = render_template(config.get("value", ""), ctx.variables)

        result = {
            "equals": str(actual) == str(value),
            "not_equals": str(actual) != str(value),
            "contains": str(value).lower() in str(actual).lower(),
            "is_empty": not str(actual).strip(),
            "not_empty": bool(str(actual).strip()),
        }.get(operator, False)

        await ctx.record("condition.evaluated", self, operator=operator, result=result)
        return NodeResult(next_handle="true" if result else "false")


class SwitchNode(BaseNode):
    type = "switch"
    label = "Switch"
    category = "logic"
    description = "Routes to an output matching the variable value"
    icon = "shuffle"
    outputs = ["default"]
    config_schema = [
        {"name": "variable", "label": "Variable", "type": "text", "required": True},
        {"name": "cases", "label": "Cases (comma separated)", "type": "text", "required": True},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        actual = str(ctx.variables.get(config.get("variable", ""), ""))
        cases = [case.strip() for case in config.get("cases", "").split(",") if case.strip()]
        handle = actual if actual in cases else "default"
        await ctx.record("switch.routed", self, handle=handle)
        return NodeResult(next_handle=handle)


class DelayNode(BaseNode):
    type = "delay"
    label = "Delay"
    category = "logic"
    description = "Waits before continuing"
    icon = "clock"
    config_schema = [
        {"name": "seconds", "label": "Seconds", "type": "number", "required": True, "default": 5},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        seconds = min(float(config.get("seconds", 5) or 0), 60.0)
        await ctx.record("delay.started", self, seconds=seconds)
        await asyncio.sleep(seconds)
        return NodeResult()


class SetVariableNode(BaseNode):
    type = "set_variable"
    label = "Set Variable"
    category = "logic"
    description = "Stores a value in the run variables"
    icon = "variable"
    config_schema = [
        {"name": "name", "label": "Variable Name", "type": "text", "required": True},
        {"name": "value", "label": "Value", "type": "text", "required": True,
         "hint": "Supports {{variables}}, e.g. '{{transcript}} (confirmed)'"},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        name = config.get("name", "")
        value = render_template(config.get("value", ""), ctx.variables)
        ctx.variables[name] = value
        await ctx.record("variable.set", self, name=name)
        return NodeResult(outputs={name: value})
