"""Speech-to-Text node (spec sections 11/26)."""
from typing import Any

from app.modules.workflows.nodes.base import BaseNode, NodeExecutionError, NodeResult


class SpeechToTextNode(BaseNode):
    type = "speech_to_text"
    label = "Speech to Text"
    category = "ai"
    description = "Transcribes recorded speech into text"
    icon = "captions"
    config_schema = [
        {"name": "language", "label": "Language", "type": "select", "required": False,
         "options": ["auto", "en", "ha", "sw", "yo", "ig", "fr", "ar"]},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        ai = ctx.services.get("ai")
        recording_url = ctx.variables.get("recording_url", "")
        language = config.get("language") or "auto"
        try:
            result = await ai.speech.transcribe(recording_url, language=language)
        except Exception as exc:
            raise NodeExecutionError(f"Speech recognition failed: {exc}") from exc
        ctx.variables["transcript"] = result.text
        ctx.variables["source_language"] = result.language or ctx.variables.get("source_language")
        await ctx.record(
            "speech.transcription.completed",
            self,
            transcript=result.text,
            language=result.language,
            provider=result.provider,
        )
        return NodeResult(outputs={"transcript": result.text})
