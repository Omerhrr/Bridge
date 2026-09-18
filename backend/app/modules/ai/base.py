"""AI service interfaces (spec §26).

The workflow layer depends only on these abstractions — never on a concrete
provider, so the AI stack can be swapped without touching workflow nodes.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class TranslationResult:
    text: str
    detected_source: str | None = None
    provider: str = "mock"


class SpeechRecognitionService(Protocol):
    def transcribe(self, audio_url: str, language: str = "auto") -> str: ...


class TranslationService(Protocol):
    def translate(self, text: str, source: str = "auto", target: str = "ha") -> TranslationResult: ...


class LanguageDetectionService(Protocol):
    def detect_language(self, text: str) -> str: ...


class SpeechSynthesisService(Protocol):
    def synthesize(self, text: str, language: str = "en") -> str:  # returns an audio URL/reference
        ...
