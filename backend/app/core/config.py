from functools import lru_cache

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
