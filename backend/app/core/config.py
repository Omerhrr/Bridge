"""Application configuration via environment variables (spec section 14)."""
import re
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def clean_sender_id(raw: str) -> str:
    """Reduce a raw sender-id/shortcode value to what Africa's Talking accepts.

    Africa's Talking sender ids and shortcodes are a single alphanumeric
    token. In practice this setting sometimes ends up holding the human
    label shown on the Africa's Talking dashboard instead, such as
    "Bridge (57000)" (a product name plus its shortcode in parentheses), or
    the webhook's own "to" field gluing a shortcode and a phone number
    together with a "+". Sending either of those straight to the API gets
    every message rejected with "InvalidSenderId", so the value is reduced
    to a single clean token before it is ever used to send.
    """
    raw = (raw or "").strip()
    if not raw:
        return ""
    # "Bridge (57000)" -> the code called out in parentheses is what the
    # account actually sends from.
    parenthesized = re.search(r"\(([A-Za-z0-9]+)\)", raw)
    if parenthesized:
        return parenthesized.group(1)
    # Otherwise keep only the first run of letters/digits, dropping
    # anything glued on after a "+", comma, space, or other separator.
    match = re.match(r"[A-Za-z0-9]+", raw)
    return match.group(0) if match else ""


# provider -> (base URL, default chat model)
_AI_PRESETS: dict[str, tuple[str, str]] = {
    "deepseek": ("https://api.deepseek.com", "deepseek-chat"),
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Application
    app_name: str = "Bridge"
    environment: str = "development"
    secret_key: str = "dev-secret-change-me"
    cors_origins: str = "*"
    seed_demo_data: bool = True

    # Database
    database_url: str = "sqlite+aiosqlite:///./bridge.db"

    @field_validator("database_url", mode="after")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        """Coerce common DATABASE_URL variants into SQLAlchemy async URLs.

        - Prisma-style SQLite ("file:...") from shared sandbox environments is
          foreign to Bridge: fall back to Bridge's own local SQLite file so the
          platform never writes into another tool's database.
        - Render/Heroku-style "postgresql://" becomes "postgresql+asyncpg://".
        """
        if value.startswith("file:"):
            return "sqlite+aiosqlite:///./bridge.db"
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    # Auth
    access_token_expire_minutes: int = 60 * 24
    auth_enabled: bool = True
    algorithm: str = "HS256"

    # Africa's Talking (spec section 25)
    at_username: str = ""
    at_api_key: str = ""
    at_phone_number: str = ""
    at_sender_id: str = ""
    # Shortcode people text (e.g. the sandbox "57000"). Used as the default
    # sender for outbound SMS so replies land in the same thread on the phone.
    at_shortcode: str = ""
    at_sandbox: bool = True
    # Acknowledge SMS webhooks immediately and run the workflow in the
    # background, so slow AI calls never make Africa's Talking retry.
    sms_background_processing: bool = True

    # AI provider (spec section 26): "deepseek", "openai", "custom" (any
    # OpenAI-compatible host via AI_BASE_URL), "stub" (offline phrasebook) or
    # "auto" (deepseek when a key is present, otherwise stub).
    ai_provider: str = "auto"
    ai_api_key: str = ""
    ai_base_url: str = ""
    ai_stt_model: str = ""
    ai_translation_model: str = ""
    ai_tts_model: str = ""

    # WhatsApp (Meta Cloud API): a second, independent inbound/outbound
    # channel alongside Africa's Talking SMS/voice/USSD. A business connects
    # its own WhatsApp Business number through Meta's developer console and
    # points its webhook at Bridge; Bridge never talks to Africa's Talking
    # for WhatsApp traffic.
    wa_phone_number_id: str = ""
    wa_access_token: str = ""
    # Arbitrary shared secret Bridge itself picks; entered in the Meta App
    # dashboard's webhook setup so Meta's verification handshake (a GET
    # request) can be checked against something only the two sides know.
    wa_verify_token: str = ""
    wa_api_version: str = "v21.0"

    # Knowledge sources may only point at public hosts unless this is set
    # (e.g. a database on the same private network as Bridge).
    allow_private_sources: bool = False
    # First account can always be created; further self-registration only
    # when this is on.
    allow_registration: bool = False
    # Required to create the first (owner) account in production, so a
    # stranger who finds the URL first can't claim the dashboard.
    setup_code: str = ""

    # Supported languages for validation (BCP-47 style codes)
    supported_languages: str = "en,ha,sw,yo,ig,am,fr,ar,zu"

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw == "*" or raw == "":
            return ["*"]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def supported_language_list(self) -> list[str]:
        return [lang.strip() for lang in self.supported_languages.split(",") if lang.strip()]

    @property
    def at_configured(self) -> bool:
        return bool(self.at_username and self.at_api_key)

    @property
    def ai_provider_resolved(self) -> str:
        provider = (self.ai_provider or "auto").strip().lower()
        if provider == "auto":
            return "deepseek" if self.ai_api_key else "stub"
        return provider

    @property
    def ai_configured(self) -> bool:
        return self.ai_provider_resolved != "stub" and bool(self.ai_api_key)

    @property
    def ai_base_url_resolved(self) -> str:
        if self.ai_base_url:
            return self.ai_base_url.rstrip("/")
        return _AI_PRESETS.get(self.ai_provider_resolved, _AI_PRESETS["openai"])[0]

    @property
    def ai_chat_model(self) -> str:
        if self.ai_translation_model:
            return self.ai_translation_model
        return _AI_PRESETS.get(self.ai_provider_resolved, _AI_PRESETS["openai"])[1]

    @property
    def default_sms_sender(self) -> str | None:
        return clean_sender_id(self.at_sender_id) or clean_sender_id(self.at_shortcode) or None

    @property
    def wa_configured(self) -> bool:
        return bool(self.wa_phone_number_id and self.wa_access_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
