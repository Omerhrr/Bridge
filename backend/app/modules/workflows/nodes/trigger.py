"""Trigger node executors.

Triggers are created by the webhooks (spec §25) and simply normalise the
incoming telecom event into run variables.
"""

from app.modules.workflows.nodes.base import RunContext, NodeResult, ServiceBag, completed


def execute_incoming_call(config: dict, ctx: RunContext, services: ServiceBag) -> NodeResult:
    return completed(detail={"caller": ctx.variables.get("caller")})


def execute_incoming_sms(config: dict, ctx: RunContext, services: ServiceBag) -> NodeResult:
    return completed(detail={"caller": ctx.variables.get("caller"), "message": ctx.variables.get("message")})


def execute_ussd_request(config: dict, ctx: RunContext, services: ServiceBag) -> NodeResult:
    return completed(detail={"session_id": ctx.variables.get("session_id")})
