"""Messaging nodes (spec section 11)."""
from typing import Any

from app.modules.workflows.nodes.base import BaseNode, NodeExecutionError, NodeResult, render_template


class SendSmsNode(BaseNode):
    type = "send_sms"
    label = "Send SMS"
    category = "messaging"
    description = "Sends an SMS message"
    icon = "send"
    config_schema = [
        {"name": "to", "label": "To", "type": "text", "required": False,
         "hint": "Leave empty to reply to the sender"},
        {"name": "text", "label": "Message Text", "type": "textarea", "required": False,
         "hint": "Leave empty to use the translated text variable"},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        comms = ctx.services.get("comms")
        to = (
            render_template(config.get("to", ""), ctx.variables)
            or ctx.variables.get("sender")
            or ctx.variables.get("caller")
            or ""
        )
        text = render_template(config.get("text", ""), ctx.variables) or ctx.variables.get("translation", "")
        if not text:
            raise NodeExecutionError("Send SMS has no message text")
        try:
            result = await comms.sms.send_sms(to=to, text=text)
        except Exception as exc:
            raise NodeExecutionError(f"Send SMS failed: {exc}") from exc
        ctx.variables["sent_sms_id"] = result.message_id
        await ctx.record(
            "sms.sent",
            self,
            to=to,
            text=text,
            simulated=result.simulated,
        )
        return NodeResult(outputs={"message_id": result.message_id})
