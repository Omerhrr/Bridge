"""AI service facade: bundles the language capabilities used by AI nodes.

The workflow engine only depends on these interfaces, never on a specific
AI provider (spec section 26).
"""
from dataclasses import dataclass

from app.modules.ai.speech import SpeechRecognitionService, get_speech_service
from app.modules.ai.synthesis import SpeechSynthesisService, get_synthesis_service
from app.modules.ai.translation import TranslationService, get_translation_service


@dataclass
class LanguageDetectionResult:
    language: str = "en"
    confidence: float = 0.5
    provider: str = "stub"


class LanguageDetectionService:
    """Interface: detect the language of a text."""

    async def detect(self, text: str) -> LanguageDetectionResult:
        raise NotImplementedError


class TranslatorLanguageDetection(LanguageDetectionService):
    """Detection backed by the active translation service (LLM or stub)."""

    def __init__(self, translation: TranslationService) -> None:
        self._translation = translation

    async def detect(self, text: str) -> LanguageDetectionResult:
        language = await self._translation.detect(text)
        return LanguageDetectionResult(language=language, confidence=0.9,
                                       provider=type(self._translation).__name__)


class AIService:
    """Facade handed to workflow nodes via the node context."""

    def __init__(self) -> None:
        self.speech: SpeechRecognitionService = get_speech_service()
        self.translation: TranslationService = get_translation_service()
        self.synthesis: SpeechSynthesisService = get_synthesis_service()
        self.detection: LanguageDetectionService = TranslatorLanguageDetection(self.translation)


def get_ai_service() -> AIService:
    return AIService()
