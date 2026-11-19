from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_WEAK_MARKERS = ("change", "secret", "password", "example", "xxxx")


class Settings(BaseSettings):
    """Configuration from environment variables only."""

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    environment: Literal["development", "test", "production"] = "production"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    secret_key: SecretStr
    database_url: SecretStr
    session_hours: int = Field(default=8, ge=1, le=72)

    # Browser origins allowed to send state-changing requests (CSRF defence in depth).
    allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["https://localhost"])
    # Host headers the app answers to ("backend" is used by Caddy's health checks).
    allowed_hosts: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["localhost", "127.0.0.1", "backend"])
    # Set when running behind exactly one trusted reverse proxy (Caddy in docker-compose).
    trust_proxy: bool = False

    rate_limit_storage_uri: SecretStr = SecretStr("memory://")
    login_rate_limit: str = "5/minute"
    register_rate_limit: str = "5/hour"
    verify_rate_limit: str = "60/hour"

    spass_path: str = "SPASS"
    vampire_path: str = "vampire"
    otter_path: str = "otter"
    max_concurrent_provers: int = Field(default=4, ge=1, le=64)
    max_time_limit: int = Field(default=30, ge=1, le=300)

    max_request_bytes: int = Field(default=262_144, ge=1024)

    @field_validator("allowed_origins", "allowed_hosts", mode="before")
    @classmethod
    def _split(cls, value: object) -> object:
        if isinstance(value, str):
            return [v.strip().rstrip("/") for v in value.split(",") if v.strip()]
        return value

    @field_validator("allowed_origins")
    @classmethod
    def _no_wildcard(cls, value: list[str]) -> list[str]:
        if "*" in value:
            raise ValueError("ALLOWED_ORIGINS must list explicit origins")
        return value

    @field_validator("secret_key")
    @classmethod
    def _strong(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if len(raw) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        if any(marker in raw.lower() for marker in _WEAK_MARKERS):
            raise ValueError("SECRET_KEY looks like a placeholder; generate a random value")
        return value

    @field_validator("database_url")
    @classmethod
    def _psycopg3(cls, value: SecretStr) -> SecretStr:
        url = value.get_secret_value()
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return SecretStr("postgresql+psycopg://" + url[len(prefix) :])
        return value

    @property
    def secure_cookies(self) -> bool:
        return self.environment == "production"
