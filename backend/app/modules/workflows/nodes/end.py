"""End node — terminates the run."""

from app.modules.workflows.nodes.base import RunContext, NodeResult, ServiceBag, completed


def execute_end(config: dict, ctx: RunContext, services: ServiceBag) -> NodeResult:
    return completed(detail={"ended": True})
