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


class StubLanguageDetection(LanguageDetectionService):
    async def detect(self, text: str) -> LanguageDetectionResult:
        from app.modules.ai.translation import StubTranslationService

        return LanguageDetectionResult(language=StubTranslationService._detect(text))


class AIService:
    """Facade handed to workflow nodes via the node context."""

    def __init__(self) -> None:
        self.speech: SpeechRecognitionService = get_speech_service()
        self.translation: TranslationService = get_translation_service()
        self.synthesis: SpeechSynthesisService = get_synthesis_service()
        self.detection: LanguageDetectionService = StubLanguageDetection()


def get_ai_service() -> AIService:
    return AIService()
