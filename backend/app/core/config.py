from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RP_", extra="ignore")
    environment: str = "development"
    database_url: SecretStr
    redis_url: SecretStr
    public_origin: str = "http://localhost:3100"
    cookie_secure: bool = False
    session_hours: int = 24
    session_idle_minutes: int = 60
    rate_namespace: str = "rp:identity"
    storage_root: Path = Path("/var/lib/researchpilot")
    google_api_key: SecretStr | None = None
    embedding_enabled: bool = False
    embedding_model: str = "gemini-embedding-2"
    embedding_dimensions: int = 768
    answer_enabled: bool = False
    answer_model: str = "gemini-3.8-flash"

    @model_validator(mode="after")
    def validate_environment(self) -> "Settings":
        if self.environment not in {"development", "test", "production"}:
            raise ValueError("Invalid environment")
        if self.environment == "production" and (
            not self.cookie_secure or not self.public_origin.startswith("https://")
        ):
            raise ValueError("Production requires HTTPS and secure cookies")
        if self.session_hours < 1 or self.session_idle_minutes < 1:
            raise ValueError("Session expiry must be positive")
        if self.embedding_model != "gemini-embedding-2" or self.embedding_dimensions != 768:
            raise ValueError("Unsupported embedding model or dimensions")
        if self.embedding_enabled and (
            self.google_api_key is None or not self.google_api_key.get_secret_value().strip()
        ):
            raise ValueError("Enabled embeddings require a server-side Google API key")
        if self.answer_enabled and (
            self.google_api_key is None or not self.google_api_key.get_secret_value().strip()
        ):
            raise ValueError("Enabled answers require a server-side Google API key")
        if not self.answer_model.startswith("gemini-") or not all(
            char.isalnum() or char in ".-" for char in self.answer_model
        ):
            raise ValueError("Invalid answer model")
        return self

    @property
    def session_cookie(self) -> str:
        return "__Host-rp_session" if self.cookie_secure else "rp_session"

    @property
    def csrf_cookie(self) -> str:
        return "__Host-rp_csrf" if self.cookie_secure else "rp_csrf"


@lru_cache
def get_settings() -> Settings:
    return Settings()
