"""Trigger nodes (spec section 11): entry points for telecom events."""
from typing import Any

from app.modules.workflows.nodes.base import BaseNode, NodeResult


class IncomingCallNode(BaseNode):
    type = "incoming_call"
    label = "Incoming Call"
    category = "trigger"
    description = "Receives a phone call"
    icon = "phone-incoming"
    inputs = []
    outputs = ["out"]
    config_schema = [
        {"name": "phone_number", "label": "Bridge Number", "type": "text", "required": False},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        payload = ctx.trigger_payload
        ctx.variables["caller"] = payload.get("caller") or payload.get("from") or "unknown"
        ctx.variables["called_number"] = payload.get("called") or config.get("phone_number", "")
        ctx.variables["channel"] = "voice"
        await ctx.record("call.received", self, caller=ctx.variables["caller"])
        return NodeResult(outputs={"caller": ctx.variables["caller"]})


class IncomingSmsNode(BaseNode):
    type = "incoming_sms"
    label = "Incoming SMS"
    category = "trigger"
    description = "Receives an SMS message"
    icon = "message-square-in"
    inputs = []
    outputs = ["out"]
    config_schema = [
        {"name": "phone_number", "label": "Bridge Number", "type": "text", "required": False},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        payload = ctx.trigger_payload
        ctx.variables["sender"] = payload.get("from") or "unknown"
        ctx.variables["text"] = payload.get("text", "")
        # The shortcode / number the SMS was sent to — replies go out from it.
        ctx.variables["shortcode"] = payload.get("called") or config.get("phone_number", "")
        ctx.variables["channel"] = "sms"
        await ctx.record("sms.received", self, sender=ctx.variables["sender"])
        return NodeResult(outputs={"text": ctx.variables["text"]})


class UssdRequestNode(BaseNode):
    type = "ussd_request"
    label = "USSD Request"
    category = "trigger"
    description = "Receives a USSD session request"
    icon = "hash"
    inputs = []
    outputs = ["out"]
    config_schema = [
        {"name": "service_code", "label": "Service Code", "type": "text", "required": False},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        payload = ctx.trigger_payload
        text = payload.get("text", "") or ""
        # Africa's Talking accumulates menu choices with "*": "1*2". The last
        # segment is the screen the user is currently answering.
        selection = text.split("*")[-1] if text else ""
        ctx.variables["session_id"] = payload.get("session_id", "")
        ctx.variables["service_code"] = payload.get("service_code", "")
        ctx.variables["phone_number"] = payload.get("phone_number") or payload.get("from") or ""
        ctx.variables["ussd_input"] = text
        ctx.variables["ussd_selection"] = selection
        ctx.variables["channel"] = "ussd"
        await ctx.record("ussd.received", self, selection=selection)
        return NodeResult(outputs={"ussd_input": text, "ussd_selection": selection})
