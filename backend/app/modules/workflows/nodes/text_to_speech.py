"""Text-to-Speech node (spec sections 11/26)."""
from typing import Any

from app.modules.workflows.nodes.base import BaseNode, NodeExecutionError, NodeResult


class TextToSpeechNode(BaseNode):
    type = "text_to_speech"
    label = "Text to Speech"
    category = "ai"
    description = "Generates speech audio from text"
    icon = "speech"
    config_schema = [
        {"name": "language", "label": "Voice Language", "type": "select", "required": False,
         "options": ["auto", "en", "ha", "sw", "yo", "ig"]},
        {"name": "voice", "label": "Voice", "type": "text", "required": False},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        ai = ctx.services.get("ai")
        text = ctx.variables.get("translation", "")
        if not text:
            raise NodeExecutionError("Text to Speech has no input text")
        language = config.get("language") or ctx.variables.get("target_language", "en")
        try:
            result = await ai.synthesis.synthesize(text, language=language, voice=config.get("voice"))
        except Exception as exc:
            raise NodeExecutionError(f"Speech synthesis failed: {exc}") from exc
        ctx.variables["audio_url"] = result.audio_url
        await ctx.record(
            "tts.generated",
            self,
            audio_url=result.audio_url,
            language=language,
            provider=result.provider,
        )
        return NodeResult(outputs={"audio_url": result.audio_url})
