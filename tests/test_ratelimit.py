from __future__ import annotations

import pytest

from snip.ratelimit import TokenBucketRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def test_allows_burst_then_blocks() -> None:
    clock = FakeClock()
    limiter = TokenBucketRateLimiter(rate=1.0, burst=3.0, clock=clock)

    assert [limiter.allow("ip") for _ in range(3)] == [True, True, True]
    assert limiter.allow("ip") is False


def test_refills_over_time() -> None:
    clock = FakeClock()
    limiter = TokenBucketRateLimiter(rate=2.0, burst=2.0, clock=clock)

    assert limiter.allow("ip") is True
    assert limiter.allow("ip") is True
    assert limiter.allow("ip") is False

    clock.advance(0.5)  # 0.5s * 2 tokens/s = 1 token
    assert limiter.allow("ip") is True
    assert limiter.allow("ip") is False


def test_refill_capped_at_burst() -> None:
    clock = FakeClock()
    limiter = TokenBucketRateLimiter(rate=5.0, burst=2.0, clock=clock)

    clock.advance(100.0)  # long idle should not overfill
    assert limiter.allow("ip") is True
    assert limiter.allow("ip") is True
    assert limiter.allow("ip") is False


def test_keys_are_independent() -> None:
    clock = FakeClock()
    limiter = TokenBucketRateLimiter(rate=1.0, burst=1.0, clock=clock)

    assert limiter.allow("a") is True
    assert limiter.allow("a") is False
    assert limiter.allow("b") is True


def test_rejects_bad_config() -> None:
    with pytest.raises(ValueError, match="rate"):
        TokenBucketRateLimiter(rate=0, burst=1)
    with pytest.raises(ValueError, match="burst"):
        TokenBucketRateLimiter(rate=1, burst=0)
