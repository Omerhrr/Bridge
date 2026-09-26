"""Language registry: the languages Bridge can translate between.

Codes are ISO 639-1 where one exists (ISO 639-3 otherwise). The list leans
towards languages spoken across Africa but covers major world languages too;
the LLM translator is not limited to it — this is what the UI offers and what
validation accepts.
"""

LANGUAGES: dict[str, str] = {
    # West Africa
    "ha": "Hausa",
    "yo": "Yoruba",
    "ig": "Igbo",
    "pcm": "Nigerian Pidgin",
    "ff": "Fulfulde",
    "tw": "Twi",
    "ee": "Ewe",
    "wo": "Wolof",
    "bm": "Bambara",
    "kr": "Kanuri",
    "efi": "Efik",
    "tiv": "Tiv",
    # East Africa
    "sw": "Swahili",
    "am": "Amharic",
    "om": "Oromo",
    "so": "Somali",
    "ti": "Tigrinya",
    "lg": "Luganda",
    "rw": "Kinyarwanda",
    "rn": "Kirundi",
    "luo": "Dholuo",
    "ki": "Kikuyu",
    # Southern Africa
    "zu": "Zulu",
    "xh": "Xhosa",
    "af": "Afrikaans",
    "st": "Sesotho",
    "tn": "Setswana",
    "sn": "Shona",
    "ny": "Chichewa",
    "ln": "Lingala",
    "mg": "Malagasy",
    # North Africa & world languages
    "ar": "Arabic",
    "en": "English",
    "fr": "French",
    "pt": "Portuguese",
    "es": "Spanish",
    "de": "German",
    "it": "Italian",
    "zh": "Chinese",
    "hi": "Hindi",
    "ru": "Russian",
    "tr": "Turkish",
}

# Special target values accepted by translate nodes and the send API.
#   contact -> the recipient's saved language (skip translation if unknown)
#   none    -> send the original text untouched
SPECIAL_TARGETS = {"contact", "none", "auto"}

_BY_NAME = {name.lower(): code for code, name in LANGUAGES.items()}
_ALIASES = {
    "pidgin": "pcm", "naija": "pcm", "kiswahili": "sw", "isizulu": "zu",
    "isixhosa": "xh", "chinese": "zh", "mandarin": "zh", "fula": "ff",
    "fulani": "ff", "luo": "luo", "sotho": "st", "tswana": "tn",
    "chichewa": "ny", "nyanja": "ny", "french": "fr", "english": "en",
}


def language_name(code: str | None) -> str:
    if not code:
        return "Unknown"
    return LANGUAGES.get(code.lower(), code)


def normalize_language(value: str | None) -> str | None:
    """Accept a code ("sw"), a name ("Swahili") or an alias ("kiswahili")."""
    if not value:
        return None
    raw = value.strip().lower()
    if raw in LANGUAGES:
        return raw
    if raw in _BY_NAME:
        return _BY_NAME[raw]
    if raw in _ALIASES:
        return _ALIASES[raw]
    # Region-tagged codes such as "en-US" / "pt_BR".
    base = raw.replace("_", "-").split("-")[0]
    if base in LANGUAGES:
        return base
    return None


def is_supported(value: str | None) -> bool:
    if not value:
        return False
    if value in SPECIAL_TARGETS or "{{" in value:
        return True
    return normalize_language(value) is not None


def language_options() -> list[dict[str, str]]:
    return [
        {"code": code, "name": name}
        for code, name in sorted(LANGUAGES.items(), key=lambda item: item[1])
    ]
