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
        {"name": "from", "label": "From (shortcode / sender ID)", "type": "text", "required": False,
         "hint": "Leave empty to reply from the shortcode the SMS arrived on"},
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
        # Reply from the same shortcode the user texted, so the answer lands in
        # the same conversation thread on their phone (and in the AT simulator)
        # instead of arriving from the account's default sender.
        sender_id = (
            render_template(config.get("from", ""), ctx.variables)
            or ctx.variables.get("shortcode")
            or None
        )
        db = ctx.services.get("db")
        if db is not None:
            # Route through the messaging service so the send is logged on the
            # Messages page alongside relay and broadcast traffic.
            from app.modules.messaging.service import MessagingService

            delivery = await MessagingService(db, ctx.services.get("ai"), comms, run_id=ctx.run_id).deliver(
                to, text, sender=sender_id, kind="reply", pretranslated=True,
                original=ctx.variables.get("text") if text == ctx.variables.get("translation") else None,
            )
            if delivery.status == "failed":
                raise NodeExecutionError(f"Send SMS failed: {delivery.error}")
            message_id, status, simulated = delivery.message_id or "", delivery.status, delivery.status == "simulated"
        else:
            try:
                result = await comms.sms.send_sms(to=to, text=text, sender_id=sender_id)
            except Exception as exc:
                raise NodeExecutionError(f"Send SMS failed: {exc}") from exc
            message_id, status, simulated = result.message_id, result.status, result.simulated
        ctx.variables["sent_sms_id"] = message_id
        await ctx.record(
            "sms.sent",
            self,
            to=to,
            sender_id=sender_id,
            text=text,
            status=status,
            simulated=simulated,
        )
        return NodeResult(outputs={"message_id": message_id})
