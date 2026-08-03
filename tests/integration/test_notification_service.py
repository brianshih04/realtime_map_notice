from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from tests.conftest import load_module


notification_service = load_module("notification_service_main", "backend/notification-service/app/main.py")


@dataclass
class FakePubSub:
    def __init__(self) -> None:
        pass

    async def subscribe(self, channel: str) -> None:
        return None

    async def get_message(self, ignore_subscribe_messages: bool = True, timeout: float = 1.0):
        return None

    async def unsubscribe(self, channel: str) -> None:
        return None

    async def close(self) -> None:
        return None


class FakeRedis:
    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    async def ping(self) -> bool:
        return True

    def pubsub(self) -> FakePubSub:
        return FakePubSub()

    async def publish(self, channel: str, message: str) -> int:
        self.published.append((channel, message))
        return 1


@pytest.mark.asyncio
async def test_healthz(monkeypatch) -> None:
    fake_redis = FakeRedis()
    monkeypatch.setattr(notification_service, "redis", fake_redis)

    transport = ASGITransport(app=notification_service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_notify_user(monkeypatch) -> None:
    fake_redis = FakeRedis()
    monkeypatch.setattr(notification_service, "redis", fake_redis)

    transport = ASGITransport(app=notification_service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/notify/u-0001",
            json={
                "event_id": "uuid",
                "title": "Urgent notice",
                "message": "Road blocked near library",
                "latitude": 25.0173,
                "longitude": 121.5397,
                "severity": "urgent",
                "distance_meters": 120.0,
            },
        )

    assert response.status_code == 200
    assert response.json()["subscriber_count"] == 1
    assert fake_redis.published[0][0] == notification_service.user_channel("u-0001")


def test_websocket_heartbeat(monkeypatch) -> None:
    fake_redis = FakeRedis()
    monkeypatch.setattr(notification_service, "redis", fake_redis)
    monkeypatch.setattr(notification_service, "HEARTBEAT_INTERVAL_SECONDS", 0)

    client = TestClient(notification_service.app)
    with client.websocket_connect("/ws/u-0001") as websocket:
        message = websocket.receive_json()

    assert message == {"type": "heartbeat", "user_id": "u-0001"}
