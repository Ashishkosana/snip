"""Base62 codec.

Encodes non-negative integers to a compact, URL-safe alphabet and back.
Pure and dependency-free so it can be unit-tested in isolation.
"""

from __future__ import annotations

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
BASE = len(ALPHABET)
_INDEX = {ch: i for i, ch in enumerate(ALPHABET)}


def encode(number: int) -> str:
    """Encode a non-negative integer to a base62 string.

    >>> encode(0)
    '0'
    >>> encode(61)
    'z'
    >>> encode(62)
    '10'
    """
    if number < 0:
        raise ValueError("number must be non-negative")
    if number == 0:
        return ALPHABET[0]
    digits: list[str] = []
    while number > 0:
        number, rem = divmod(number, BASE)
        digits.append(ALPHABET[rem])
    return "".join(reversed(digits))


def decode(text: str) -> int:
    """Decode a base62 string back to an integer.

    >>> decode("10")
    62
    """
    if not text:
        raise ValueError("empty string is not a valid base62 value")
    number = 0
    for ch in text:
        try:
            number = number * BASE + _INDEX[ch]
        except KeyError as exc:
            raise ValueError(f"invalid base62 character: {ch!r}") from exc
    return number
