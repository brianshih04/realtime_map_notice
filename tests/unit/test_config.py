import os
import importlib

import backend.shared.config as config


class TestConfig:
    def test_default_redis_url(self):
        assert config.REDIS_URL == "redis://localhost:6379/0"

    def test_custom_redis_url(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://custom-host:6380/1")
        importlib.reload(config)
        assert config.REDIS_URL == "redis://custom-host:6380/1"
        # Restore
        monkeypatch.delenv("REDIS_URL")
        importlib.reload(config)

    def test_cors_allow_origins_default(self):
        origins = config.CORS_ALLOW_ORIGINS
        assert "http://localhost:5173" in origins
        assert "http://localhost:3000" in origins

    def test_cors_allow_origins_custom(self, monkeypatch):
        monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://example.com,https://app.io")
        importlib.reload(config)
        assert "https://example.com" in config.CORS_ALLOW_ORIGINS
        assert "https://app.io" in config.CORS_ALLOW_ORIGINS
        monkeypatch.delenv("CORS_ALLOW_ORIGINS")
        importlib.reload(config)

    def test_default_alert_radius(self):
        assert config.DEFAULT_ALERT_RADIUS_METERS == 500

    def test_user_location_key(self):
        assert config.USER_LOCATION_KEY == "realtime_map_notice:user:locations"
