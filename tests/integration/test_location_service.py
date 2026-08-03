from __future__ import annotations

from dataclasses import dataclass

import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import load_module


location_service = load_module("location_service_main", "backend/location-service/app/main.py")


@dataclass
class FakeRedis:
    geoadd_calls: list[tuple[str, tuple[float, float, str]]]
    set_calls: list[tuple[str, str, int | None]]
    geosearch_result: list[str]

    def __init__(self) -> None:
        self.geoadd_calls = []
        self.set_calls = []
        self.geosearch_result = []

    async def ping(self) -> bool:
        return True

    async def geoadd(self, key: str, value: tuple[float, float, str]) -> int:
        self.geoadd_calls.append((key, value))
        return 1

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.set_calls.append((key, value, ex))
        return True

    async def geosearch(self, *args, **kwargs):
        return self.geosearch_result


@pytest.mark.asyncio
async def test_healthz(monkeypatch) -> None:
    fake_redis = FakeRedis()
    monkeypatch.setattr(location_service, "redis", fake_redis)

    transport = ASGITransport(app=location_service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_update_location(monkeypatch) -> None:
    fake_redis = FakeRedis()
    monkeypatch.setattr(location_service, "redis", fake_redis)

    transport = ASGITransport(app=location_service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/locations",
            json={"user_id": "u-0001", "latitude": 25.0173, "longitude": 121.5397},
        )

    assert response.status_code == 200
    assert response.json()["user_id"] == "u-0001"
    assert fake_redis.geoadd_calls == [
        (
            location_service.USER_LOCATION_KEY,
            (121.5397, 25.0173, "u-0001"),
        )
    ]
    assert fake_redis.set_calls[0][0] == "realtime_map_notice:user:last_seen:u-0001"
    assert fake_redis.set_calls[0][2] == location_service.LAST_SEEN_TTL_SECONDS


@pytest.mark.asyncio
async def test_get_nearby_users(monkeypatch) -> None:
    fake_redis = FakeRedis()
    fake_redis.geosearch_result = ["u-0001", "u-0002"]
    monkeypatch.setattr(location_service, "redis", fake_redis)

    transport = ASGITransport(app=location_service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/locations/nearby",
            params={"latitude": 25.0173, "longitude": 121.5397, "radius_meters": 500},
        )

    assert response.status_code == 200
    assert response.json() == {"users": ["u-0001", "u-0002"]}


@pytest.mark.asyncio
async def test_get_nearby_users_no_result(monkeypatch) -> None:
    fake_redis = FakeRedis()
    fake_redis.geosearch_result = []
    monkeypatch.setattr(location_service, "redis", fake_redis)

    transport = ASGITransport(app=location_service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/locations/nearby",
            params={"latitude": 25.0173, "longitude": 121.5397, "radius_meters": 500},
        )

    assert response.status_code == 200
    assert response.json() == {"users": []}
