"""Messaging node executors."""

from app.modules.workflows.nodes.base import (
    RunContext,
    NodeResult,
    ServiceBag,
    render_template,
    resolve_value,
    completed,
)


def execute_send_sms(config: dict, ctx: RunContext, services: ServiceBag) -> NodeResult:
    to = render_template(config.get("to", "") or "{{caller}}", ctx.variables)
    message = resolve_value(config, ctx.variables, "message", var_key="from_variable")
    if not message:
        return NodeResult(status="failed", detail={"error": "send_sms: no message provided"})
    message = render_template(str(message), ctx.variables)
    result = services.comms.send_sms(to=to, message=message, conversation_id=ctx.variables.get("_conversation_id"))
    ctx.actions.append({"action": "SendSMS", "to": to, "message": message})
    return completed(output={"sms_sent_to": to}, detail={"to": to, "message": message, "provider": result.get("provider")})
