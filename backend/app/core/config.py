"""Application configuration via environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", env_prefix="BRIDGE_"
    )

    # --- Application ------------------------------------------------------
    app_name: str = "Bridge"
    environment: str = "development"
    debug: bool = True

    # --- Database ---------------------------------------------------------
    # PostgreSQL in production (Render), SQLite for local development/tests.
    database_url: str = "sqlite:///./bridge.db"

    # --- Security ---------------------------------------------------------
    # Optional bearer token guarding mutating /api/workflows operations.
    api_token: str | None = None

    # --- Africa's Talking -------------------------------------------------
    at_username: str | None = None
    at_api_key: str | None = None
    at_sender_id: str | None = None
    at_base_url: str = "https://api.africastalking.com/version1"

    # --- AI providers -----------------------------------------------------
    # "mock" provider is used when no real provider is configured.
    ai_provider: str = "mock"

    # --- Communications ---------------------------------------------------
    # "mock" records actions locally; "africastalking" performs real requests.
    comms_provider: str = "mock"


@lru_cache
def get_settings() -> Settings:
    return Settings()
