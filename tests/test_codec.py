from __future__ import annotations

import pytest

from snip import codec


@pytest.mark.parametrize("n", [0, 1, 61, 62, 63, 12345, 62**7 - 1, 10**18])
def test_roundtrip(n: int) -> None:
    assert codec.decode(codec.encode(n)) == n


def test_zero_is_single_char() -> None:
    assert codec.encode(0) == "0"


def test_encode_rejects_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        codec.encode(-1)


def test_decode_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        codec.decode("")


def test_decode_rejects_bad_char() -> None:
    with pytest.raises(ValueError, match="invalid base62"):
        codec.decode("abc$")


def test_uniqueness_over_range() -> None:
    codes = {codec.encode(i) for i in range(100_000)}
    assert len(codes) == 100_000


def test_monotonic_length_growth() -> None:
    assert len(codec.encode(61)) == 1
    assert len(codec.encode(62)) == 2
    assert len(codec.encode(62 * 62)) == 3
