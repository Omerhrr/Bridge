"""Translation node (spec sections 11/26)."""
from typing import Any

from app.modules.workflows.nodes.base import BaseNode, NodeExecutionError, NodeResult


class TranslateNode(BaseNode):
    type = "translate"
    label = "Translate"
    category = "ai"
    description = "Translates text between languages"
    icon = "languages"
    config_schema = [
        {"name": "source_language", "label": "Source Language", "type": "select",
         "required": False, "options": ["auto", "en", "ha", "sw", "yo", "ig", "fr", "ar"],
         "default": "auto"},
        {"name": "target_language", "label": "Target Language", "type": "select",
         "required": True, "options": ["en", "ha", "sw", "yo", "ig", "fr", "ar"]},
        {"name": "provider", "label": "Provider", "type": "select", "required": False,
         "options": ["default", "stub"]},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        ai = ctx.services.get("ai")
        text = ctx.variables.get("transcript") or ctx.variables.get("text", "")
        if not text:
            raise NodeExecutionError("Translate has no input text")
        source = config.get("source_language") or "auto"
        target = config.get("target_language") or ctx.variables.get("target_language", "en")
        try:
            result = await ai.translation.translate(text, source=source, target=target)
        except Exception as exc:
            raise NodeExecutionError(f"Translation failed: {exc}") from exc
        ctx.variables["translation"] = result.text
        ctx.variables["source_language"] = result.source
        ctx.variables["target_language"] = result.target
        await ctx.record(
            "translation.completed",
            self,
            source=result.source,
            target=result.target,
            text=result.text,
            provider=result.provider,
        )
        return NodeResult(outputs={"translation": result.text})
