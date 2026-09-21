"""Application configuration via environment variables (spec section 14)."""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    at_sandbox: bool = True

    # AI provider (spec section 26)
    ai_provider: str = "stub"
    ai_api_key: str = ""
    ai_base_url: str = ""
    ai_stt_model: str = ""
    ai_translation_model: str = ""
    ai_tts_model: str = ""

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
    def ai_configured(self) -> bool:
        return self.ai_provider != "stub" and bool(self.ai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
