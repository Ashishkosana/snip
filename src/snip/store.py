"""Storage layer.

Defines a narrow :class:`StorePort` protocol so the FastAPI routes depend on an
interface, not a database. Two implementations are provided:

* :class:`SqliteStore` - the production adapter (SQLModel / SQLite).
* :class:`InMemoryStore` - a dependency-free adapter used by unit tests.

Both share the same collision-safe base62 code generation: a random integer is
encoded to base62 and inserted; on a unique-constraint conflict we simply retry
with a fresh random id.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from snip import codec
from snip.models import Link, utcnow

# Random id space for code generation. 62**7 ~= 3.5e12 keeps codes short (<=7
# chars) while making collisions astronomically unlikely at portfolio scale.
_CODE_ID_SPACE = 62**7


class CodeGenerationError(RuntimeError):
    """Raised when a unique code could not be generated within the retry budget."""


def _random_code() -> str:
    return codec.encode(secrets.randbelow(_CODE_ID_SPACE))


@runtime_checkable
class StorePort(Protocol):
    """The storage contract the application depends on."""

    def create(self, url: str, expires_at: datetime | None, *, max_retries: int) -> Link:
        """Persist a new link with a freshly generated, unique code."""
        ...

    def get(self, code: str) -> Link | None:
        """Return the link for ``code`` or ``None`` if unknown."""
        ...

    def increment_clicks(self, code: str) -> Link | None:
        """Atomically bump the click counter and return the updated link."""
        ...


def _normalise(link: Link) -> Link:
    """Ensure datetimes are tz-aware (SQLite drops tzinfo on round-trip)."""
    if link.created_at.tzinfo is None:
        link.created_at = link.created_at.replace(tzinfo=UTC)
    if link.expires_at is not None and link.expires_at.tzinfo is None:
        link.expires_at = link.expires_at.replace(tzinfo=UTC)
    return link


class SqliteStore:
    """SQLModel-backed store."""

    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(database_url, connect_args=connect_args)
        SQLModel.metadata.create_all(self._engine)

    def create(self, url: str, expires_at: datetime | None, *, max_retries: int) -> Link:
        for _ in range(max_retries):
            link = Link(code=_random_code(), url=url, expires_at=expires_at)
            with Session(self._engine) as session:
                session.add(link)
                try:
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    continue
                session.refresh(link)
                return _normalise(link)
        raise CodeGenerationError("exhausted retries generating a unique code")

    def get(self, code: str) -> Link | None:
        with Session(self._engine) as session:
            link = session.exec(select(Link).where(Link.code == code)).first()
            return _normalise(link) if link is not None else None

    def increment_clicks(self, code: str) -> Link | None:
        with Session(self._engine) as session:
            link = session.exec(select(Link).where(Link.code == code)).first()
            if link is None:
                return None
            link.clicks += 1
            session.add(link)
            session.commit()
            session.refresh(link)
            return _normalise(link)


class InMemoryStore:
    """Dict-backed store with the same semantics, for tests."""

    def __init__(self) -> None:
        self._by_code: dict[str, Link] = {}
        self._next_id = 1

    def create(self, url: str, expires_at: datetime | None, *, max_retries: int) -> Link:
        for _ in range(max_retries):
            code = _random_code()
            if code in self._by_code:
                continue
            link = Link(
                id=self._next_id,
                code=code,
                url=url,
                expires_at=expires_at,
                created_at=utcnow(),
            )
            self._next_id += 1
            self._by_code[code] = link
            return link
        raise CodeGenerationError("exhausted retries generating a unique code")

    def get(self, code: str) -> Link | None:
        return self._by_code.get(code)

    def increment_clicks(self, code: str) -> Link | None:
        link = self._by_code.get(code)
        if link is None:
            return None
        link.clicks += 1
        return link
