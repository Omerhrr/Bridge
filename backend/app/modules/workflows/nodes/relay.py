"""Bridge Relay node: cross-language SMS chat through the Bridge shortcode."""
from typing import Any

from app.modules.messaging.service import MessagingService
from app.modules.workflows.nodes.base import BaseNode, NodeExecutionError, NodeResult


class BridgeRelayNode(BaseNode):
    type = "bridge_relay"
    label = "Bridge Relay"
    category = "messaging"
    description = (
        "Lets two people chat by SMS in different languages. Handles TO, LANG, "
        "STOP and HELP commands and translates every message for the reader."
    )
    icon = "arrow-left-right"
    config_schema = []

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        db = ctx.services.get("db")
        if db is None:
            raise NodeExecutionError("Bridge Relay needs a database session")
        service = MessagingService(db, ctx.services.get("ai"), ctx.services.get("comms"), run_id=ctx.run_id)
        sender = ctx.variables.get("sender") or ""
        if not sender or sender == "unknown":
            raise NodeExecutionError("Bridge Relay needs the sender's phone number")
        outcome = await service.handle_relay(sender, ctx.variables.get("shortcode"), ctx.variables.get("text", ""))
        failed = [d for d in outcome.deliveries if d.status == "failed"]
        ctx.variables["relay_action"] = outcome.action
        await ctx.record(
            "relay.handled", self, action=outcome.action,
            deliveries=[{"to": d.to, "status": d.status, "language": d.target_language,
                         "error": d.error} for d in outcome.deliveries],
        )
        if failed and len(failed) == len(outcome.deliveries):
            raise NodeExecutionError(f"Bridge Relay could not deliver: {failed[0].error}")
        return NodeResult(outputs={"relay_action": outcome.action})
