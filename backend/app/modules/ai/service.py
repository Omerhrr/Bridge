"""AI service factory — selects the configured provider (spec §26)."""

from functools import lru_cache

from app.core.config import get_settings
from app.modules.ai.mock import MockAIProvider


class AIService:
    """Facade exposing the four AI capabilities to workflow nodes."""

    def __init__(self, provider):
        self.provider = provider

    def transcribe(self, audio_url: str, language: str = "auto") -> str:
        return self.provider.transcribe(audio_url, language=language)

    def translate(self, text: str, source: str = "auto", target: str = "ha"):
        return self.provider.translate(text, source=source, target=target)

    def detect_language(self, text: str) -> str:
        return self.provider.detect_language(text)

    def synthesize(self, text: str, language: str = "en") -> str:
        return self.provider.synthesize(text, language=language)


@lru_cache
def get_ai_service() -> AIService:
    settings = get_settings()
    # Only the mock provider ships with the MVP; real providers plug in here.
    provider = MockAIProvider()
    return AIService(provider)
