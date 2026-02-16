"""API key generation and hashing utilities.

Keys follow the format ``otr_<64-hex-chars>`` so they are easy to
recognise and rotate.  Only the SHA-256 hash is persisted in the
database; the raw key is shown exactly once at creation time.
"""

import hashlib
import secrets

from app.registry.constants import API_KEY_PREFIX, API_KEY_RANDOM_BYTES


def generate_api_key() -> str:
    """Return a new random API key string (e.g. ``otr_ab12cd...``)."""
    raw = secrets.token_hex(API_KEY_RANDOM_BYTES)
    return f"{API_KEY_PREFIX}{raw}"


def hash_api_key(raw_key: str) -> str:
    """Produce the SHA-256 hex digest used for database storage."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def key_prefix(raw_key: str) -> str:
    """Extract the display prefix (e.g. ``otr_ab12``) from a raw key."""
    return raw_key[: len(API_KEY_PREFIX) + 4]
