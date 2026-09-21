"""Translation service interface and stub provider (spec section 26)."""
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.logging import get_logger, log_event

logger = get_logger("bridge.ai.translation")


@dataclass
class TranslationResult:
    text: str
    source: str = "en"
    target: str = "ha"
    provider: str = "stub"


# Tiny phrasebook so the hackathon demo (spec sections 5/7) shows real output
# when no AI provider is configured. Real provider replaces this seamlessly.
_PHRASEBOOK: dict[tuple[str, str], dict[str, str]] = {
    ("en", "ha"): {
        "where are you?": "Ina kake?",
        "where are you": "Ina kake?",
        "hello": "Sannu",
        "how are you?": "Kana lahiya?",
        "how are you": "Kana lahiya?",
        "good morning": "Ina kwana",
        "thank you": "Na gode",
        "i am coming": "Ina zuwa",
        "how much is this?": "Nawa ne wannan?",
        "call me": "Kira ni",
    },
    ("ha", "en"): {
        "ina kake?": "Where are you?",
        "ina kake": "Where are you?",
        "sannu": "Hello",
        "kana lahiya?": "How are you?",
        "kana lahiya": "How are you?",
        "ina kwana": "Good morning",
        "na gode": "Thank you",
        "ina zuwa": "I am coming",
        "nawa ne wannan?": "How much is this?",
        "kira ni": "Call me",
    },
}


class TranslationService:
    """Interface: translate text between languages."""

    async def translate(self, text: str, source: str = "auto", target: str = "en") -> TranslationResult:
        raise NotImplementedError


class StubTranslationService(TranslationService):
    """Development provider: phrasebook lookup with marker fallback."""

    async def translate(self, text: str, source: str = "auto", target: str = "en") -> TranslationResult:
        detected = source if source not in ("", "auto") else self._detect(text)
        table = _PHRASEBOOK.get((detected, target), {})
        lowered = text.strip().lower()
        translated = table.get(lowered)
        if translated is None:
            translated = f"[{detected}→{target}] {text}"
        log_event(logger, "translation.completed", provider="stub", source=detected, target=target)
        return TranslationResult(text=translated, source=detected, target=target, provider="stub")

    @staticmethod
    def _detect(text: str) -> str:
        markers = {"ina": "ha", "kake": "ha", "sannu": "ha", "na gode": "ha", "the": "en", "you": "en", "where": "en"}
        lowered = text.lower()
        for marker, lang in markers.items():
            if marker in lowered:
                return lang
        return "en"


class HttpTranslationService(TranslationService):
    """Provider skeleton for an OpenAI-compatible chat translation API."""

    async def translate(self, text: str, source: str = "auto", target: str = "en") -> TranslationResult:
        if not settings.ai_api_key:
            raise RuntimeError("AI_API_KEY is not configured")
        language_names = {"en": "English", "ha": "Hausa", "sw": "Swahili", "yo": "Yoruba",
                          "ig": "Igbo", "fr": "French", "ar": "Arabic"}
        target_name = language_names.get(target, target)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.ai_base_url or 'https://api.openai.com/v1'}/chat/completions",
                headers={"Authorization": f"Bearer {settings.ai_api_key}"},
                json={
                    "model": settings.ai_translation_model or "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": f"Translate the user text to {target_name}. Reply with the translation only."},
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        translated = data["choices"][0]["message"]["content"].strip()
        return TranslationResult(text=translated, source=source, target=target, provider="openai")


def get_translation_service() -> TranslationService:
    if settings.ai_configured:
        return HttpTranslationService()
    return StubTranslationService()
