"""FastAPI application and HTTP routes.

The app is built by a factory so tests can inject an :class:`InMemoryStore` and
a deterministic rate limiter. Routes stay thin: validation lives in the pydantic
models, code generation in the store, and throttling in the token bucket.
"""

from datetime import timedelta
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse

from snip.config import Settings, get_settings
from snip.models import ShortenRequest, ShortenResponse, StatsResponse, utcnow
from snip.ratelimit import TokenBucketRateLimiter
from snip.store import CodeGenerationError, SqliteStore, StorePort


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def create_app(
    store: StorePort | None = None,
    limiter: TokenBucketRateLimiter | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    store = store or SqliteStore(settings.database_url)
    limiter = limiter or TokenBucketRateLimiter(
        rate=settings.rate_limit_per_second,
        burst=settings.rate_limit_burst,
    )

    app = FastAPI(title="snip", version="0.1.0", description="A tiny URL shortener.")

    def get_store() -> StorePort:
        return store

    def get_limiter() -> TokenBucketRateLimiter:
        return limiter

    def get_config() -> Settings:
        return settings

    StoreDep = Annotated[StorePort, Depends(get_store)]
    LimiterDep = Annotated[TokenBucketRateLimiter, Depends(get_limiter)]
    ConfigDep = Annotated[Settings, Depends(get_config)]

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/shorten", response_model=ShortenResponse, status_code=201)
    def shorten(
        payload: ShortenRequest,
        request: Request,
        store: StoreDep,
        limiter: LimiterDep,
        config: ConfigDep,
    ) -> ShortenResponse:
        if not limiter.allow(_client_ip(request)):
            raise HTTPException(status_code=429, detail="rate limit exceeded")

        ttl_days = payload.ttl_days if payload.ttl_days is not None else config.default_ttl_days
        expires_at = utcnow() + timedelta(days=ttl_days) if ttl_days is not None else None

        try:
            link = store.create(
                str(payload.url),
                expires_at,
                max_retries=config.max_code_generation_retries,
            )
        except CodeGenerationError as exc:
            raise HTTPException(status_code=503, detail="could not allocate a code") from exc

        return ShortenResponse(
            code=link.code,
            short_url=f"{config.base_url.rstrip('/')}/{link.code}",
        )

    @app.get("/api/{code}", response_model=StatsResponse)
    def stats(code: str, store: StoreDep) -> StatsResponse:
        link = store.get(code)
        if link is None:
            raise HTTPException(status_code=404, detail="unknown code")
        return StatsResponse(
            url=link.url,
            clicks=link.clicks,
            created_at=link.created_at,
            expires_at=link.expires_at,
        )

    @app.get("/{code}")
    def redirect(code: str, store: StoreDep) -> RedirectResponse:
        link = store.get(code)
        if link is None:
            raise HTTPException(status_code=404, detail="unknown code")
        if link.expires_at is not None and link.expires_at <= utcnow():
            raise HTTPException(status_code=410, detail="link expired")

        updated = store.increment_clicks(code)
        target = updated.url if updated is not None else link.url
        return RedirectResponse(url=target, status_code=307)

    return app


app = create_app()
