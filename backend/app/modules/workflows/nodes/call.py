"""Voice nodes (spec section 11): call control and playback."""
from typing import Any

from app.modules.workflows.nodes.base import BaseNode, NodeExecutionError, NodeResult


class MakeCallNode(BaseNode):
    type = "make_call"
    label = "Make Call"
    category = "voice"
    description = "Places an outbound call"
    icon = "phone-outgoing"
    config_schema = [
        {"name": "to", "label": "Destination Number", "type": "text", "required": True},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        comms = ctx.services.get("comms")
        to = config.get("to") or ctx.variables.get("callee", "")
        try:
            result = await comms.voice.make_call(to=to)
        except Exception as exc:  # provider not configured / network failure
            raise NodeExecutionError(f"Make Call failed: {exc}") from exc
        ctx.variables["call_id"] = result.call_id
        await ctx.record("call.started", self, to=to, simulated=result.simulated)
        return NodeResult(outputs={"call_id": result.call_id})


class CollectSpeechNode(BaseNode):
    type = "collect_speech"
    label = "Collect Speech"
    category = "voice"
    description = "Records speech from the caller"
    icon = "mic"
    config_schema = [
        {"name": "max_duration", "label": "Max Duration (seconds)", "type": "number", "required": False, "default": 15},
        {"name": "finish_on_key", "label": "Finish On Key", "type": "text", "required": False, "default": "#"},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        recording_url = ctx.trigger_payload.get("recording_url") or ctx.variables.get("recording_url", "")
        if not recording_url:
            # In the live voice loop the next webhook carries the recording;
            # during test runs we continue with an empty recording.
            await ctx.record("call.waiting_for_speech", self)
        ctx.variables["recording_url"] = recording_url
        return NodeResult(outputs={"recording_url": recording_url})


class PlayAudioNode(BaseNode):
    type = "play_audio"
    label = "Play Audio"
    category = "voice"
    description = "Plays an audio file to the caller"
    icon = "audio-lines"
    config_schema = [
        {"name": "url", "label": "Audio URL", "type": "text", "required": True},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        await ctx.record("call.play_audio", self, url=config.get("url", ""))
        return NodeResult()


class PlayTextNode(BaseNode):
    type = "play_text"
    label = "Play Text"
    category = "voice"
    description = "Reads text aloud to the caller"
    icon = "text-cursor-input"
    config_schema = [
        {"name": "text", "label": "Text", "type": "text", "required": True},
        {"name": "language", "label": "Language", "type": "select", "required": False, "options": ["en", "ha", "sw", "yo", "ig"]},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        await ctx.record("call.play_text", self, text=config.get("text", ""))
        return NodeResult()


class PlayVoiceNode(BaseNode):
    type = "play_voice"
    label = "Play Voice"
    category = "voice"
    description = "Plays generated speech audio to the caller"
    icon = "volume-2"
    config_schema = []

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        audio_url = ctx.variables.get("audio_url", "")
        text = ctx.variables.get("translation", "")
        await ctx.record(
            "call.played_voice",
            self,
            audio_url=audio_url,
            text=text,
            simulated=audio_url.startswith("stub://"),
        )
        return NodeResult(outputs={"played": True})


class HangUpNode(BaseNode):
    type = "hang_up"
    label = "Hang Up"
    category = "voice"
    description = "Ends the call"
    icon = "phone-off"
    outputs = []

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        await ctx.record("call.completed", self)
        return NodeResult()
