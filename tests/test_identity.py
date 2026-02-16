"""Unit tests for identity domain logic (no database required)."""

from app.registry.security import generate_api_key, hash_api_key, key_prefix


def test_generate_api_key_format() -> None:
    key = generate_api_key()
    assert key.startswith("otr_")
    assert len(key) == 4 + 64  # prefix + 32 bytes hex


def test_hash_api_key_deterministic() -> None:
    key = "otr_abc123"
    h1 = hash_api_key(key)
    h2 = hash_api_key(key)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex digest


def test_key_prefix_extraction() -> None:
    key = "otr_abcdef1234567890"
    prefix = key_prefix(key)
    assert prefix == "otr_abcd"
