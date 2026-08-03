from __future__ import annotations

from dataclasses import dataclass

import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import load_module


event_service = load_module("event_service_main", "backend/event-service/app/main.py")


@dataclass
class FakePipeline:
    values: dict[str, str | None]
    requested_keys: list[str]

    def __init__(self, values: dict[str, str | None]) -> None:
        self.values = values
        self.requested_keys = []

    def get(self, key: str) -> "FakePipeline":
        self.requested_keys.append(key)
        return self

    async def execute(self) -> list[str | None]:
        return [
            self.values.get(key)
            for key in self.requested_keys
        ]
    
class FakeRedis:
    def __init__(self) -> None:
        self.geosearch_result = []
        self.pipeline_values: dict[str, str | None] = {}
        self.pipeline_instance: FakePipeline | None = None
        self.set_calls = []
        self.geoadd_calls = []
        self.zrem_calls = []

    async def ping(self) -> bool:
        return True

    async def set(self, key, value, ex=None):
        self.set_calls.append(
            {
                "key": key,
                "value": value,
                "ex": ex,
            }
        )

    async def geosearch(self, *args, **kwargs):
        return self.geosearch_result

    async def geoadd(self, key, values):
        self.geoadd_calls.append(
            {
                "key": key,
                "values": values,
            }
        )

    async def zrem(self, key, *members):
        self.zrem_calls.append(
            {
                "key": key,
                "members": members,
            }
        )

    def pipeline(self, transaction: bool = False) -> FakePipeline:
        self.pipeline_instance = FakePipeline(self.pipeline_values)
        return self.pipeline_instance


class FakeAsyncClient:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self.posts: list[tuple[str, dict[str, object]]] = []

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, json: dict[str, object]):
        self.posts.append((url, json))

        class Response:
            status_code = 200

        return Response()


@pytest.mark.asyncio
async def test_healthz(monkeypatch) -> None:
    fake_redis = FakeRedis()
    monkeypatch.setattr(event_service, "redis", fake_redis)

    transport = ASGITransport(app=event_service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_create_event_with_nearby_users(monkeypatch) -> None:
    fake_redis = FakeRedis()
    fake_redis.geosearch_result = [("u-0001", "120.0"), ("u-0002", "250.0")]
    fake_redis.pipeline_values = {
        f"{event_service.USER_LAST_SEEN_PREFIX}:u-0001": "2026-07-05T00:00:00Z",
        f"{event_service.USER_LAST_SEEN_PREFIX}:u-0002": None,
    }
    monkeypatch.setattr(event_service, "redis", fake_redis)

    fake_client = FakeAsyncClient(timeout=3.0)
    monkeypatch.setattr(event_service.httpx, "AsyncClient", lambda timeout=3.0: fake_client)

    transport = ASGITransport(app=event_service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/events",
            json={
                "title": "Library seats",
                "message": "3F has seats near windows",
                "latitude": 25.0173,
                "longitude": 121.5397,
                "severity": "urgent",
                "radius_meters": 500,
                "duration_minutes": 60,
                "image_base64": "fake-image-base64-data",
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["nearby_user_count"] == 2
    assert body["active_user_count"] == 1
    assert body["delivered_count"] == 1
    assert body["delivered_to"] == ["u-0001"]
    assert fake_redis.pipeline_instance is not None
    assert fake_redis.pipeline_instance.requested_keys == [
        f"{event_service.USER_LAST_SEEN_PREFIX}:u-0001",
        f"{event_service.USER_LAST_SEEN_PREFIX}:u-0002",
    ]
    assert len(fake_client.posts) == 1
    sent_payload = fake_client.posts[0][1]
    assert sent_payload["image_base64"] == "fake-image-base64-data"
    assert len(fake_redis.set_calls) == 1
    assert fake_redis.set_calls[0]["ex"] == 60 * 60
    assert len(fake_redis.geoadd_calls) == 1
    assert fake_redis.geoadd_calls[0]["key"] == "event_locations"
    assert fake_redis.geoadd_calls[0]["values"][0] == 121.5397
    assert fake_redis.geoadd_calls[0]["values"][1] == 25.0173


@pytest.mark.asyncio
async def test_create_event_no_nearby_users(monkeypatch) -> None:
    fake_redis = FakeRedis()
    fake_redis.geosearch_result = []
    monkeypatch.setattr(event_service, "redis", fake_redis)

    fake_client = FakeAsyncClient(timeout=3.0)
    monkeypatch.setattr(event_service.httpx, "AsyncClient", lambda timeout=3.0: fake_client)

    transport = ASGITransport(app=event_service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/events",
            json={
                "title": "Library seats",
                "message": "3F has seats near windows",
                "latitude": 25.0173,
                "longitude": 121.5397,
                "severity": "info",
                "radius_meters": 500,
                "duration_minutes": 30,
                "image_base64": None,
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["nearby_user_count"] == 0
    assert body["active_user_count"] == 0
    assert body["delivered_count"] == 0
    assert body["delivered_to"] == []
    assert fake_client.posts == []
    assert len(fake_redis.geoadd_calls) == 1
    assert fake_redis.geoadd_calls[0]["key"] == "event_locations"
    assert fake_redis.geoadd_calls[0]["values"][0] == 121.5397
    assert fake_redis.geoadd_calls[0]["values"][1] == 25.0173


@pytest.mark.asyncio
async def test_get_events(monkeypatch) -> None:
    fake_redis = FakeRedis()

    fake_redis.geosearch_result = [
        "event-001",
    ]

    fake_redis.pipeline_values = {
        "event:event-001": """
        {
            "title": "Library 3F has seats",
            "message": "About 10 seats near windows.",
            "severity": "info",
            "latitude": 24.6859,
            "longitude": 120.9123,
            "radius_meters": 500,
            "created_at": "2026-08-02T01:30:00+00:00"
        }
        """
    }

    monkeypatch.setattr(
        event_service,
        "redis",
        fake_redis,
    )

    transport = ASGITransport(app=event_service.app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/events",
            params={
                "latitude": 24.6859,
                "longitude": 120.9123,
                "radius": 3000,
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1

    assert body[0]["event_id"] == "event-001"
    assert body[0]["title"] == "Library 3F has seats"
    assert body[0]["severity"] == "info"
    assert body[0]["radius_meters"] == 500
    assert body[0]["created_at"] == "2026-08-02T01:30:00+00:00"


@pytest.mark.asyncio
async def test_get_events_invalid_latitude(monkeypatch) -> None:
    transport = ASGITransport(app=event_service.app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/events",
            params={
                "latitude": 100,
                "longitude": 121.5,
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_events_empty(monkeypatch) -> None:
    fake_redis = FakeRedis()
    fake_redis.geosearch_result = []

    monkeypatch.setattr(
        event_service,
        "redis",
        fake_redis,
    )

    transport = ASGITransport(app=event_service.app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/events",
            params={
                "latitude": 25.0173,
                "longitude": 121.5397,
            },
        )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_events_remove_expired_events(monkeypatch) -> None:
    fake_redis = FakeRedis()

    fake_redis.geosearch_result = [
        "expired-event-001",
    ]

    fake_redis.pipeline_values = {
        "event:expired-event-001": None,
    }

    monkeypatch.setattr(
        event_service,
        "redis",
        fake_redis,
    )

    transport = ASGITransport(app=event_service.app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/events",
            params={
                "latitude": 24.6859,
                "longitude": 120.9123,
                "radius": 3000,
            },
        )

    assert response.status_code == 200
    assert response.json() == []

    assert fake_redis.zrem_calls == [
        {
            "key": "event_locations",
            "members": ("expired-event-001",),
        }
    ]
