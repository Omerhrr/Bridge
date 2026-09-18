"""Mock AI provider.

Deterministic, dependency-free implementations used in development and tests.
The mock dictionary covers the demo pairs (English <-> Hausa, English <->
Swahili); unknown text passes through with a marker so the pipeline remains
observable end-to-end.
"""

import hashlib

from app.modules.ai.base import TranslationResult

# Small demo dictionary — enough to make the hackathon demo legible.
DICT_EN_HA = {
    "where are you": "ina kake",
    "where are you?": "ina kake",
    "hello": "sannu",
    "good morning": "ina kwana",
    "how are you": "ya kake",
    "how are you?": "ya kake",
    "thank you": "na gode",
    "what is your name": "menene sunanka",
    "i am coming": "ina zuwa",
    "how much is this": "nawa ne wannan",
    "we are waiting for you": "muna jiran ka",
}
DICT_HA_EN = {v: k for k, v in DICT_EN_HA.items()}
DICT_EN_SW = {
    "where are you": "uko wapi",
    "where are you?": "uko wapi",
    "hello": "hujambo",
    "good morning": "habari za asubuhi",
    "how are you": "habari yako",
    "thank you": "asante",
    "i am coming": "naja",
}
DICT_SW_EN = {v: k for k, v in DICT_EN_SW.items()}


class MockAIProvider:
    """SpeechRecognition + Translation + Detection + Synthesis in one object."""

    name = "mock"

    # --- Speech recognition --------------------------------------------
    def transcribe(self, audio_url: str, language: str = "auto") -> str:
        """Returns a deterministic demo transcript derived from the reference."""
        digest = hashlib.sha1(audio_url.encode()).hexdigest()
        sample = ["Where are you?", "How are you?", "Thank you very much", "I am coming now"]
        return sample[int(digest[:2], 16) % len(sample)]

    # --- Translation ------------------------------------------------------
    def translate(self, text: str, source: str = "auto", target: str = "ha") -> TranslationResult:
        detected = self.detect_language(text) if source in ("auto", None, "") else source
        translated = self._translate_text(text.strip(), detected, target)
        return TranslationResult(text=translated, detected_source=detected, provider=self.name)

    def _translate_text(self, text: str, source: str, target: str) -> str:
        if source == target:
            return text
        key = text.lower().strip().rstrip("?.!")
        if source == "en" and target == "ha":
            return DICT_EN_HA.get(key, DICT_EN_HA.get(key + "?", f"[ha] {text}"))
        if source == "ha" and target == "en":
            return DICT_HA_EN.get(key, f"[en] {text}")
        if source == "en" and target == "sw":
            return DICT_EN_SW.get(key, f"[sw] {text}")
        if source == "sw" and target == "en":
            return DICT_SW_EN.get(key, f"[en] {text}")
        return f"[{target}] {text}"

    # --- Language detection ------------------------------------------------
    def detect_language(self, text: str) -> str:
        lowered = text.lower().strip()
        for phrase in DICT_HA_EN:
            if phrase in lowered:
                return "ha"
        for phrase in DICT_SW_EN:
            if phrase in lowered:
                return "sw"
        return "en"

    # --- Speech synthesis ----------------------------------------------------
    def synthesize(self, text: str, language: str = "en") -> str:
        """Returns a deterministic pseudo audio reference for the demo."""
        digest = hashlib.sha1(f"{language}:{text}".encode()).hexdigest()[:10]
        return f"https://audio.bridge.local/tts/{language}-{digest}.mp3"
