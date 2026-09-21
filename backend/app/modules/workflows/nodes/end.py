"""Flow nodes (spec section 11): explicit end marker."""
from typing import Any

from app.modules.workflows.nodes.base import BaseNode, NodeResult


class EndNode(BaseNode):
    type = "end"
    label = "End"
    category = "flow"
    description = "Marks the end of the workflow"
    icon = "square"
    outputs = []

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        await ctx.record("workflow.reached_end", self)
        return NodeResult()
