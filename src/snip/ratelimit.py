"""In-process token-bucket rate limiter.

A classic token bucket: each key gets a bucket that holds up to ``burst``
tokens and refills at ``rate`` tokens per second. A request consumes one
token; when the bucket is empty the request is rejected.

The limiter is deliberately monotonic-clock based and injectable so tests can
drive time deterministically instead of sleeping.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


@dataclass
class TokenBucketRateLimiter:
    """Per-key token bucket.

    Args:
        rate: tokens refilled per second.
        burst: maximum tokens a bucket can hold (the burst allowance).
        clock: monotonic time source, injectable for tests.
    """

    rate: float
    burst: float
    clock: Callable[[], float] = time.monotonic
    _buckets: dict[str, _Bucket] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def __post_init__(self) -> None:
        if self.rate <= 0:
            raise ValueError("rate must be positive")
        if self.burst <= 0:
            raise ValueError("burst must be positive")

    def allow(self, key: str, cost: float = 1.0) -> bool:
        """Try to consume ``cost`` tokens for ``key``. Return True if allowed."""
        now = self.clock()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(tokens=self.burst, updated_at=now)
                self._buckets[key] = bucket

            elapsed = max(0.0, now - bucket.updated_at)
            bucket.tokens = min(self.burst, bucket.tokens + elapsed * self.rate)
            bucket.updated_at = now

            if bucket.tokens >= cost:
                bucket.tokens -= cost
                return True
            return False

    def reset(self) -> None:
        """Drop all buckets (useful between tests)."""
        with self._lock:
            self._buckets.clear()
