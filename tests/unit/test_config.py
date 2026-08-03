from __future__ import annotations

from tests.conftest import load_module


def test_default_redis_url(monkeypatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    config = load_module("backend_shared_config_default", "backend/shared/config.py")

    assert config.REDIS_URL == "redis://localhost:6379/0"


def test_custom_redis_url(monkeypatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://example:6379/1")
    config = load_module("backend_shared_config_custom", "backend/shared/config.py")

    assert config.REDIS_URL == "redis://example:6379/1"


def test_default_last_seen_ttl(monkeypatch) -> None:
    monkeypatch.delenv("LAST_SEEN_TTL_SECONDS", raising=False)
    config = load_module("backend_shared_config_ttl", "backend/shared/config.py")

    assert config.LAST_SEEN_TTL_SECONDS == 60


def test_custom_last_seen_ttl(monkeypatch) -> None:
    monkeypatch.setenv("LAST_SEEN_TTL_SECONDS", "120")
    config = load_module("backend_shared_config_custom_ttl", "backend/shared/config.py")

    assert config.LAST_SEEN_TTL_SECONDS == 120
