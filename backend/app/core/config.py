import re
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.embedder import contract as local_embedder

# OpenRouter ids look like "vendor/model" with optional ":free"/":variant" suffix.
OPENROUTER_MODEL = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}/[A-Za-z0-9][A-Za-z0-9._-]{0,127}(?::[a-z]{1,20})?")


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
    # google: Gemini API (needs a key, text leaves the server); local: open-weights Qwen3
    # served by the internal embedder container (no key, text stays on the server).
    embedding_provider: Literal["google", "local"] = "google"
    embedding_url: str = "http://embedder:8000"
    answer_enabled: bool = False
    answer_provider: Literal["google", "openrouter"] = "google"
    answer_model: str = "gemini-3.8-flash"
    openrouter_api_key: SecretStr | None = None
    # Shared across all users: a free provider quota belongs to one server key.
    answer_daily_limit: int = 20
    # Per-user share of that budget. Unset means the whole budget (single-user use);
    # set it lower before letting other researchers register.
    answer_user_daily_limit: int | None = None
    # Private research: by default OpenRouter routes only to hosts that do not
    # collect prompts. Some free models have no such host; allow explicitly if needed.
    openrouter_allow_data_collection: bool = False

    @field_validator("answer_user_daily_limit", mode="before")
    @classmethod
    def empty_means_unset(cls, value: object) -> object:
        # Compose forwards an unset optional variable as an empty string.
        return None if isinstance(value, str) and not value.strip() else value

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
        url = urlsplit(self.embedding_url)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
            raise ValueError("Embedding URL must be a plain http(s) service address")
        if self.embedding_enabled and self.embedding_provider == "google" and (
            self.google_api_key is None or not self.google_api_key.get_secret_value().strip()
        ):
            raise ValueError("Enabled embeddings require a server-side Google API key")
        if self.answer_enabled and not self.answer_key:
            raise ValueError("Enabled answers require a server-side key for the answer provider")
        if self.answer_provider == "google" and (
            not self.answer_model.startswith("gemini-")
            or not all(char.isalnum() or char in ".-" for char in self.answer_model)
        ):
            raise ValueError("Invalid answer model")
        if self.answer_provider == "openrouter" and not OPENROUTER_MODEL.fullmatch(
            self.answer_model
        ):
            raise ValueError("Invalid answer model")
        if not 1 <= self.answer_daily_limit <= 100_000:
            raise ValueError("Answer daily limit must be between 1 and 100000")
        if self.answer_user_daily_limit is not None and not (
            1 <= self.answer_user_daily_limit <= self.answer_daily_limit
        ):
            raise ValueError("Per-user answer limit must be between 1 and the daily limit")
        return self

    @property
    def embedding_model(self) -> str:
        return local_embedder.MODEL if self.embedding_provider == "local" else "gemini-embedding-2"

    @property
    def answer_user_limit(self) -> int:
        return self.answer_user_daily_limit or self.answer_daily_limit

    @property
    def answer_key(self) -> str | None:
        secret = self.openrouter_api_key if self.answer_provider == "openrouter" else self.google_api_key
        value = secret.get_secret_value().strip() if secret else ""
        return value or None

    @property
    def session_cookie(self) -> str:
        return "__Host-rp_session" if self.cookie_secure else "rp_session"

    @property
    def csrf_cookie(self) -> str:
        return "__Host-rp_csrf" if self.cookie_secure else "rp_csrf"


@lru_cache
def get_settings() -> Settings:
    return Settings()
