"""Set Variable and Condition were the only nodes in the palette that didn't
support {{variables}} in their configured values, unlike every other node
(Send SMS, Translate, USSD screens, ...). Confirms both now render templates
consistently, so a workflow can build a value from earlier variables or
compare against one.
"""
import pytest

from app.modules.workflows.nodes.base import NodeContext
from app.modules.workflows.nodes.condition import ConditionNode, SetVariableNode


def _ctx(**variables):
    return NodeContext(run_id="run_test", variables=variables)


@pytest.mark.asyncio
async def test_set_variable_renders_template():
    ctx = _ctx(transcript="I need help")
    result = await SetVariableNode().execute({"name": "note", "value": "{{transcript}} (confirmed)"}, ctx)
    assert ctx.variables["note"] == "I need help (confirmed)"
    assert result.outputs == {"note": "I need help (confirmed)"}


@pytest.mark.asyncio
async def test_condition_compares_against_rendered_variable():
    ctx = _ctx(ussd_selection="2", expected_choice="2")
    result = await ConditionNode().execute(
        {"variable": "ussd_selection", "operator": "equals", "value": "{{expected_choice}}"}, ctx
    )
    assert result.next_handle == "true"


@pytest.mark.asyncio
async def test_condition_still_supports_a_literal_value():
    ctx = _ctx(ussd_selection="1")
    result = await ConditionNode().execute(
        {"variable": "ussd_selection", "operator": "equals", "value": "1"}, ctx
    )
    assert result.next_handle == "true"
