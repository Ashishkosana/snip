from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from snip.models import utcnow
from snip.store import InMemoryStore, SqliteStore
from tests.test_ratelimit import FakeClock

LONG_URL = "https://example.com/a/very/long/path"


def _shorten(client: TestClient, url: str = LONG_URL) -> dict[str, str]:
    resp = client.post("/api/shorten", json={"url": url})
    assert resp.status_code == 201, resp.text
    data: dict[str, str] = resp.json()
    return data


def test_create_redirect_and_click_count(client: TestClient) -> None:
    body = _shorten(client)
    code = body["code"]
    assert body["short_url"] == f"http://short.test/{code}"

    resp = client.get(f"/{code}", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "https://example.com/a/very/long/path"

    client.get(f"/{code}", follow_redirects=False)

    stats = client.get(f"/api/{code}")
    assert stats.status_code == 200
    assert stats.json()["clicks"] == 2
    assert stats.json()["url"] == "https://example.com/a/very/long/path"


def test_unknown_code_redirect_404(client: TestClient) -> None:
    assert client.get("/nope", follow_redirects=False).status_code == 404


def test_unknown_code_stats_404(client: TestClient) -> None:
    assert client.get("/api/nope").status_code == 404


def test_invalid_url_rejected(client: TestClient) -> None:
    resp = client.post("/api/shorten", json={"url": "not-a-url"})
    assert resp.status_code == 422


def test_ftp_scheme_rejected(client: TestClient) -> None:
    resp = client.post("/api/shorten", json={"url": "ftp://example.com/file"})
    assert resp.status_code == 422


def test_expired_link_returns_410(client: TestClient, store: InMemoryStore) -> None:
    link = store.create("https://example.com", utcnow() - timedelta(seconds=1), max_retries=8)
    resp = client.get(f"/{link.code}", follow_redirects=False)
    assert resp.status_code == 410


def test_ttl_is_recorded(client: TestClient) -> None:
    resp = client.post("/api/shorten", json={"url": "https://example.com", "ttl_days": 7})
    code = resp.json()["code"]
    stats = client.get(f"/api/{code}").json()
    assert stats["expires_at"] is not None


def test_rate_limit_returns_429(client: TestClient, clock: FakeClock) -> None:
    # burst=3 configured in the fixture, so the 4th call within the same
    # instant must be throttled.
    for _ in range(3):
        assert client.post("/api/shorten", json={"url": "https://example.com"}).status_code == 201
    blocked = client.post("/api/shorten", json={"url": "https://example.com"})
    assert blocked.status_code == 429

    clock.advance(1.0)  # rate=1/s refills one token
    assert client.post("/api/shorten", json={"url": "https://example.com"}).status_code == 201


def test_sqlite_store_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    store = SqliteStore(f"sqlite:///{db}")
    link = store.create("https://example.com", None, max_retries=8)
    fetched = store.get(link.code)
    assert fetched is not None
    assert fetched.url == "https://example.com"
    assert store.increment_clicks(link.code) is not None
    assert store.get(link.code).clicks == 1  # type: ignore[union-attr]
