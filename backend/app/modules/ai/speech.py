"""Speech recognition service interface and stub provider (spec section 26)."""
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.logging import get_logger, log_event

logger = get_logger("bridge.ai.speech")


@dataclass
class SpeechResult:
    text: str
    language: str | None = None
    provider: str = "stub"


class SpeechRecognitionService:
    """Interface: transcribe audio into text."""

    async def transcribe(self, audio_url: str, language: str = "auto") -> SpeechResult:
        raise NotImplementedError


class StubSpeechRecognition(SpeechRecognitionService):
    """Development provider: no external AI needed.

    If a trigger payload carries a transcript (e.g. from the test console),
    it is used directly. Otherwise a placeholder transcript is produced so
    the workflow can be exercised end to end without an AI key.
    """

    async def transcribe(self, audio_url: str, language: str = "auto") -> SpeechResult:
        if not audio_url:
            return SpeechResult(
                text="[no speech recorded]", language=language if language != "auto" else "en",
                provider="stub",
            )
        log_event(logger, "speech.transcription.completed", provider="stub", audio_url=audio_url)
        return SpeechResult(text="[transcribed speech]", language="en", provider="stub")


class HttpSpeechRecognition(SpeechRecognitionService):
    """Provider skeleton for an OpenAI-compatible transcription API.

    Transcription APIs accept audio bytes, not URLs, so the audio is
    downloaded from the recording URL first and uploaded as multipart data.
    """

    async def transcribe(self, audio_url: str, language: str = "auto") -> SpeechResult:
        if not settings.ai_api_key:
            raise RuntimeError("AI_API_KEY is not configured")
        if not audio_url:
            raise RuntimeError("No recording URL supplied to the transcription step")
        async with httpx.AsyncClient(timeout=60) as client:
            audio = await client.get(audio_url)
            audio.raise_for_status()
            suffix = audio_url.rsplit(".", 1)[-1][:4] or "mp3"
            resp = await client.post(
                f"{settings.ai_base_url or 'https://api.openai.com/v1'}/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.ai_api_key}"},
                files={"audio": (f"recording.{suffix}", audio.content, "application/octet-stream")},
                data={"model": settings.ai_stt_model or "whisper-1"},
            )
            resp.raise_for_status()
            data = resp.json()
        return SpeechResult(text=data.get("text", ""), language=language, provider="openai")


def get_speech_service() -> SpeechRecognitionService:
    if settings.ai_configured:
        return HttpSpeechRecognition()
    return StubSpeechRecognition()
