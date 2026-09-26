"""WhatsApp messaging node (Meta Cloud API): the outbound half of the
incoming_whatsapp trigger, kept in its own module since sms.py is already
mixed with the messaging-service-backed relay logic that doesn't apply here."""
from typing import Any

from app.modules.workflows.nodes.base import BaseNode, NodeExecutionError, NodeResult, render_template


class SendWhatsappNode(BaseNode):
    type = "send_whatsapp"
    label = "Send WhatsApp"
    category = "messaging"
    description = "Sends a WhatsApp text message"
    icon = "message-circle"
    config_schema = [
        {"name": "to", "label": "To", "type": "text", "required": False,
         "hint": "Leave empty to reply to the sender"},
        {"name": "text", "label": "Message Text", "type": "textarea", "required": False,
         "hint": "Leave empty to use the translated text variable"},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        comms = ctx.services.get("comms")
        to = render_template(config.get("to", ""), ctx.variables) or ctx.variables.get("sender") or ""
        if not to:
            raise NodeExecutionError("Send WhatsApp has no recipient")
        text = render_template(config.get("text", ""), ctx.variables) or ctx.variables.get("translation", "")
        if not text:
            raise NodeExecutionError("Send WhatsApp has no message text")
        try:
            result = await comms.whatsapp.send_text(to=to, text=text)
        except Exception as exc:
            raise NodeExecutionError(f"Send WhatsApp failed: {exc}") from exc
        ctx.variables["sent_whatsapp_id"] = result.message_id
        await ctx.record(
            "whatsapp.sent", self, to=to, text=text, status=result.status, simulated=result.simulated,
        )
        return NodeResult(outputs={"message_id": result.message_id})
