"""Translation service interface and stub provider (spec section 26)."""
from dataclasses import dataclass

from app.core.config import settings
from app.modules.ai.languages import language_name, normalize_language
from app.modules.ai.llm import LLMError, chat_json
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

    async def detect(self, text: str) -> str:
        raise NotImplementedError


class StubTranslationService(TranslationService):
    """Development provider: phrasebook lookup with marker fallback."""

    async def translate(self, text: str, source: str = "auto", target: str = "en") -> TranslationResult:
        detected = source if source not in ("", "auto") else self._detect(text)
        if detected == target:
            return TranslationResult(text=text, source=detected, target=target, provider="stub")
        table = _PHRASEBOOK.get((detected, target), {})
        lowered = text.strip().lower()
        translated = table.get(lowered)
        if translated is None:
            translated = f"[{detected}→{target}] {text}"
        log_event(logger, "translation.completed", provider="stub", source=detected, target=target)
        return TranslationResult(text=translated, source=detected, target=target, provider="stub")

    async def detect(self, text: str) -> str:
        return self._detect(text)

    @staticmethod
    def _detect(text: str) -> str:
        markers = {"ina": "ha", "kake": "ha", "sannu": "ha", "na gode": "ha", "the": "en", "you": "en", "where": "en"}
        lowered = text.lower()
        for marker, lang in markers.items():
            if marker in lowered:
                return lang
        return "en"


class LLMTranslationService(TranslationService):
    """Translation through an OpenAI-compatible chat model (DeepSeek by default).

    One call both detects the source language and translates, so callers get
    the sender's language for free (used to learn contact preferences).
    """

    SYSTEM = (
        "You are Bridge, a professional translator for SMS and USSD messages "
        "between people across Africa and the world. Translate faithfully and "
        "naturally, keep names, numbers, amounts, dates and phone numbers "
        "exactly as written, keep it concise (SMS), and never add commentary. "
        "Respond only with a json object: {\"detected_language\": <ISO 639-1 code of "
        "the input, or ISO 639-3 if no 2-letter code exists, e.g. 'pcm' for "
        "Nigerian Pidgin>, \"translation\": <the translated text>}."
    )

    async def translate(self, text: str, source: str = "auto", target: str = "en") -> TranslationResult:
        target_code = normalize_language(target) or target
        source_hint = (
            f"The input is written in {language_name(source)}. "
            if source not in ("", "auto", None) else ""
        )
        data = await chat_json(
            self.SYSTEM,
            f"{source_hint}Translate into {language_name(target_code)} ({target_code}).\n\n"
            f"Text:\n{text}",
        )
        translated = str(data.get("translation") or "").strip()
        if not translated:
            raise LLMError("AI provider returned an empty translation")
        detected = normalize_language(str(data.get("detected_language") or "")) or (
            source if source not in ("", "auto", None) else "und"
        )
        log_event(logger, "translation.completed", provider=settings.ai_provider_resolved,
                  source=detected, target=target_code)
        return TranslationResult(text=translated, source=detected, target=target_code,
                                 provider=settings.ai_provider_resolved)

    async def detect(self, text: str) -> str:
        data = await chat_json(
            "Identify the language of the user's text. Respond only with a json object "
            "{\"language\": <ISO 639-1 code, or ISO 639-3 if no 2-letter code exists>}.",
            text,
            max_tokens=20,
        )
        return normalize_language(str(data.get("language") or "")) or "und"


def get_translation_service() -> TranslationService:
    if settings.ai_configured:
        return LLMTranslationService()
    return StubTranslationService()
