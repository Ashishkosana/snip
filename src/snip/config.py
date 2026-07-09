"""Application configuration via pydantic-settings.

Values can be overridden with ``SNIP_`` prefixed environment variables, e.g.
``SNIP_DATABASE_URL`` or ``SNIP_RATE_LIMIT_PER_SECOND``.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SNIP_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./snip.db"
    base_url: str = "http://localhost:8000"

    # Token bucket for POST /api/shorten, keyed by client IP.
    rate_limit_per_second: float = 5.0
    rate_limit_burst: float = 10.0

    # Bounds for the optional per-link TTL.
    default_ttl_days: int | None = None
    max_code_generation_retries: int = 8


@lru_cache
def get_settings() -> Settings:
    return Settings()
