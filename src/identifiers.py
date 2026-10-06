"""Generation and validation of prefixed ULID identifiers for memory records."""

from __future__ import annotations

import secrets
import time

_ALLOWED_PREFIXES = frozenset({"prj", "epi", "sem", "rev", "les", "lnk"})
_CROCKFORD_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_prefixed_ulid(prefix: str, *, timestamp_ms: int | None = None) -> str:
    """Create a sortable, canonical ULID with an entity prefix."""

    if prefix not in _ALLOWED_PREFIXES:
        raise ValueError(f"unsupported identifier prefix: {prefix}")
    timestamp_ms = int(time.time() * 1000) if timestamp_ms is None else timestamp_ms
    if not 0 <= timestamp_ms < 2**48:
        raise ValueError("timestamp_ms must fit in a 48-bit ULID timestamp")
    value = (timestamp_ms << 80) | int.from_bytes(secrets.token_bytes(10))
    return f"{prefix}_{_encode_base32(value, 26)}"


def is_prefixed_ulid(value: str, prefix: str) -> bool:
    """Return whether *value* is a canonical `prefix_` plus 26-char ULID."""

    if prefix not in _ALLOWED_PREFIXES or not isinstance(value, str):
        return False
    expected_prefix = f"{prefix}_"
    if not value.startswith(expected_prefix) or len(value) != len(expected_prefix) + 26:
        return False
    suffix = value[len(expected_prefix) :]
    return suffix[0] in "01234567" and all(character in _CROCKFORD_BASE32 for character in suffix)


def require_prefixed_ulid(value: str, prefix: str) -> str:
    """Validate and return a prefixed ULID for use in Pydantic validators."""

    if not is_prefixed_ulid(value, prefix):
        raise ValueError(f"must be a canonical {prefix}_ ULID")
    return value


def _encode_base32(value: int, length: int) -> str:
    characters = ["0"] * length
    for index in range(length - 1, -1, -1):
        characters[index] = _CROCKFORD_BASE32[value & 31]
        value >>= 5
    return "".join(characters)
