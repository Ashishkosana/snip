"""Data model and API schemas.

``Link`` is the persisted SQLModel table. The ``*Request``/``*Response``
models are the pydantic v2 schemas that shape the HTTP surface.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel


def utcnow() -> datetime:
    """Timezone-aware UTC now (SQLite loses tzinfo, so we normalise on read)."""
    return datetime.now(UTC)


class Link(SQLModel, table=True):
    """A shortened link row.

    ``id`` is the monotonically increasing primary key; the public ``code`` is
    a base62 rendering of a random id so codes are neither guessable-sequential
    nor collision-prone.
    """

    id: int | None = SQLField(default=None, primary_key=True)
    code: str = SQLField(index=True, unique=True)
    url: str
    clicks: int = SQLField(default=0)
    created_at: datetime = SQLField(default_factory=utcnow)
    expires_at: datetime | None = SQLField(default=None)


class ShortenRequest(BaseModel):
    url: AnyHttpUrl
    ttl_days: int | None = Field(default=None, ge=1, le=3650)

    @field_validator("url")
    @classmethod
    def _reject_unsupported_scheme(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.scheme not in {"http", "https"}:
            raise ValueError("only http and https URLs are supported")
        return value


class ShortenResponse(BaseModel):
    code: str
    short_url: str


class StatsResponse(BaseModel):
    url: str
    clicks: int
    created_at: datetime
    expires_at: datetime | None
