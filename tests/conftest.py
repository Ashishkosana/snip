from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from snip.app import create_app
from snip.config import Settings
from snip.ratelimit import TokenBucketRateLimiter
from snip.store import InMemoryStore
from tests.test_ratelimit import FakeClock


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def client(store: InMemoryStore, clock: FakeClock) -> Iterator[TestClient]:
    settings = Settings(base_url="http://short.test")
    limiter = TokenBucketRateLimiter(rate=1.0, burst=3.0, clock=clock)
    app = create_app(store=store, limiter=limiter, settings=settings)
    with TestClient(app) as test_client:
        yield test_client
