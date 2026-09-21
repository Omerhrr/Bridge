"""Airtime node (hackathon track: Airtime & customer incentives)."""
from typing import Any

from app.modules.workflows.nodes.base import BaseNode, NodeExecutionError, NodeResult, render_template


class SendAirtimeNode(BaseNode):
    type = "send_airtime"
    label = "Send Airtime"
    category = "telecom"
    description = "Sends airtime as a reward or incentive"
    icon = "smartphone"
    config_schema = [
        {"name": "to", "label": "Phone Number", "type": "text", "required": False,
         "hint": "Leave empty to reward the sender/caller"},
        {"name": "amount", "label": "Amount", "type": "text", "required": True, "default": "10"},
        {"name": "currency_code", "label": "Currency", "type": "select", "required": False,
         "options": ["KES", "NGN", "GHS", "UGX", "TZS", "RWF", "ZMW", "XOF"],
         "default": "KES"},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        comms = ctx.services.get("comms")
        to = (
            render_template(config.get("to", ""), ctx.variables)
            or ctx.variables.get("sender")
            or ctx.variables.get("caller")
            or ""
        )
        amount = render_template(config.get("amount", ""), ctx.variables)
        currency = config.get("currency_code", "KES")
        if not to:
            raise NodeExecutionError("Send Airtime has no destination phone number")
        if not amount:
            raise NodeExecutionError("Send Airtime has no amount configured")
        try:
            result = await comms.airtime.send_airtime(to=to, amount=amount, currency_code=currency)
        except Exception as exc:
            raise NodeExecutionError(f"Send Airtime failed: {exc}") from exc

        ctx.variables["airtime_status"] = result.status
        ctx.variables["airtime_transaction_id"] = result.transaction_id
        await ctx.record(
            "airtime.sent", self, to=to, amount=f"{currency} {amount}",
            transaction_id=result.transaction_id, simulated=result.simulated,
        )
        return NodeResult(outputs={
            "airtime_status": result.status,
            "airtime_transaction_id": result.transaction_id,
        })
