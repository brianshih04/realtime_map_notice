"""Integration test fixtures using fakeredis + FastAPI ASGITransport.

Services are imported via importlib because folder names use hyphens
(e.g. location-service/) which cannot be normal Python imports.

All services share a single FakeAsyncRedis instance so that GEOADD in
location-service is visible to GEOSEARCH in event-service.
"""

import importlib.util
import os
from pathlib import Path

import pytest_asyncio
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient

BACKEND = Path(__file__).resolve().parent.parent.parent / "backend"

# Module-level shared fakeredis — all fixtures use this same instance
_shared_redis = FakeAsyncRedis()


def _load_app(service_name: str):
    """Import a FastAPI app from backend/<service-name>/app/main.py.

    The module-level create_redis() must already be patched to return
    the shared fakeredis before calling this.
    """
    app_path = BACKEND / service_name / "app" / "main.py"
    spec = importlib.util.spec_from_file_location(f"{service_name}.main", app_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.app


# ---------------------------------------------------------------------------
# Location Service
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def location_client():
    """FastAPI test client for location-service with shared fakeredis."""
    import backend.shared.redis_client as rc

    original = rc.create_redis
    rc.create_redis = lambda: _shared_redis

    app = _load_app("location-service")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    rc.create_redis = original


# ---------------------------------------------------------------------------
# Event Service
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def event_client():
    """FastAPI test client for event-service with shared fakeredis + mocked HTTP."""
    import httpx

    import backend.shared.redis_client as rc

    original_create_redis = rc.create_redis
    rc.create_redis = lambda: _shared_redis

    # Mock the notification service URL via env
    os.environ["NOTIFICATION_SERVICE_URL"] = "http://mock-notify:9999"

    app = _load_app("event-service")

    # Intercept calls to /notify/{user_id} with a mock transport
    def _mock_handler(request):
        return httpx.Response(200, json={"status": "published"})

    original_async_client = httpx.AsyncClient

    def _patched_async_client(**kwargs):
        return original_async_client(
            transport=httpx.MockTransport(_mock_handler),
            base_url="http://mock-notify:9999",
            **kwargs,
        )

    httpx.AsyncClient = _patched_async_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Restore
    httpx.AsyncClient = original_async_client
    rc.create_redis = original_create_redis
    os.environ.pop("NOTIFICATION_SERVICE_URL", None)


# ---------------------------------------------------------------------------
# Notification Service
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def notification_client():
    """FastAPI test client for notification-service with shared fakeredis."""
    import backend.shared.redis_client as rc

    original = rc.create_redis
    rc.create_redis = lambda: _shared_redis

    app = _load_app("notification-service")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    rc.create_redis = original
