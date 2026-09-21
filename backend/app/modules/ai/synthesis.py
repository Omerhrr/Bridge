"""Speech synthesis service interface and stub provider (spec section 26)."""
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.logging import get_logger, log_event

logger = get_logger("bridge.ai.synthesis")


@dataclass
class SynthesisResult:
    audio_url: str
    provider: str = "stub"


class SpeechSynthesisService:
    """Interface: generate speech audio from text."""

    async def synthesize(self, text: str, language: str = "en", voice: str | None = None) -> SynthesisResult:
        raise NotImplementedError


class StubSpeechSynthesis(SpeechSynthesisService):
    """Development provider: returns a marker URL instead of real audio."""

    async def synthesize(self, text: str, language: str = "en", voice: str | None = None) -> SynthesisResult:
        log_event(logger, "tts.generated", provider="stub", language=language, chars=len(text))
        digest = abs(hash((text, language))) % 10_000_000
        return SynthesisResult(audio_url=f"stub://tts/{language}/{digest}", provider="stub")


class HttpSpeechSynthesis(SpeechSynthesisService):
    """Provider skeleton for an OpenAI-compatible TTS API."""

    async def synthesize(self, text: str, language: str = "en", voice: str | None = None) -> SynthesisResult:
        if not settings.ai_api_key:
            raise RuntimeError("AI_API_KEY is not configured")
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.ai_base_url or 'https://api.openai.com/v1'}/audio/speech",
                headers={"Authorization": f"Bearer {settings.ai_api_key}"},
                json={
                    "model": settings.ai_tts_model or "tts-1",
                    "voice": voice or "alloy",
                    "input": text,
                },
            )
            resp.raise_for_status()
        # In production the audio bytes would be uploaded to storage and a URL returned.
        log_event(logger, "tts.generated", provider="openai", language=language)
        return SynthesisResult(audio_url="openai://audio/speech", provider="openai")


def get_synthesis_service() -> SpeechSynthesisService:
    if settings.ai_configured:
        return HttpSpeechSynthesis()
    return StubSpeechSynthesis()
