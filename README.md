# snip

**A tiny, production-quality URL shortener — collision-safe base62 codes, per-IP token-bucket rate limiting, and a clean hexagonal core, all behind FastAPI.**

No AI, no magic — just the backend fundamentals done carefully: a pure codec, a testable rate limiter, a storage port with swappable adapters, strict typing, and green CI.

## Why it's interesting

- **Collision-safe codes.** Short codes are base62 renderings of a random id from a `62**7` space; inserts retry on a unique-constraint conflict, so two links never share a code.
- **Real rate limiting.** A per-client token bucket (configurable `rate`/`burst`) throttles `POST /api/shorten` and returns `429` when a caller is too eager. The clock is injectable, so the behaviour is unit-tested deterministically instead of with `sleep`.
- **Ports & adapters.** Routes depend on a narrow `StorePort` protocol. Production uses `SqliteStore` (SQLModel); tests use an `InMemoryStore` — same semantics, zero I/O.
- **Typed and tested.** `ruff` + `mypy --strict` + `pytest`, run on Python 3.11 and 3.13 in CI.

## Quickstart

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# run the checks
ruff check . && mypy && pytest

# run the server
snip                       # or: uvicorn snip.app:app --reload
```

Docker:

```bash
docker compose up --build
```

## API

| Method | Path            | Purpose                                                        |
| ------ | --------------- | -------------------------------------------------------------- |
| POST   | `/api/shorten`  | `{url, ttl_days?}` → `{code, short_url}` (rate-limited by IP)  |
| GET    | `/{code}`       | `307` redirect to the long URL; bumps the click counter        |
| GET    | `/api/{code}`   | stats: `{url, clicks, created_at, expires_at}`                 |
| GET    | `/health`       | liveness probe                                                 |

Redirects return `404` for unknown codes and `410` once a link's TTL has passed.

## Curl demo

```bash
# shorten
curl -s -X POST localhost:8000/api/shorten \
  -H 'content-type: application/json' \
  -d '{"url": "https://example.com/some/really/long/link", "ttl_days": 30}'
# -> {"code":"3 Kf9Qa","short_url":"http://localhost:8000/3kf9Qa"}

# follow the redirect (note the 307 + Location header)
curl -sI localhost:8000/3kf9Qa

# read the stats
curl -s localhost:8000/api/3kf9Qa
# -> {"url":"https://...","clicks":1,"created_at":"...","expires_at":"..."}
```

## Design notes

- **`codec.py`** — pure base62 encode/decode with property-style roundtrip tests. Kept dependency-free so the interesting logic is trivial to reason about and test.
- **`ratelimit.py`** — a `TokenBucketRateLimiter` keyed by client IP. Tokens refill continuously at `rate`/s up to `burst`; each request costs one token. Thread-safe via a lock; time comes from an injectable `clock`.
- **`store.py`** — the `StorePort` protocol plus `SqliteStore` and `InMemoryStore`. Code generation and collision-retry live here, behind the port, so routes stay thin. SQLite loses `tzinfo`, so datetimes are normalised to UTC on read.
- **`models.py`** — the `Link` table and the pydantic v2 request/response schemas. URL validation (and http/https-only enforcement) is declarative on the schema.
- **`app.py`** — a `create_app(store, limiter, settings)` factory. Dependency injection makes the whole HTTP surface testable with an in-memory store and a fake clock via FastAPI's `TestClient`.
- **`config.py`** — `pydantic-settings`; every knob is overridable with a `SNIP_`-prefixed env var.

### Trade-offs / what I'd add next

- The rate limiter is in-process, so it's per-instance. Behind multiple replicas you'd move the bucket to Redis (same interface).
- Click counting is a synchronous `UPDATE`; a high-traffic version would batch/async it or use a counter store.
- Codes are random; a sharded sequential-id + base62 scheme would give shorter codes with zero retry, at the cost of guessability.

## License

MIT © Ashish Kosana
