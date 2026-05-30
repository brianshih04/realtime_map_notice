"""Cross-service test: Location Service → Redis → nearby query.

Requires: docker compose up -d (real Redis + services)
"""

import pytest


@pytest.mark.asyncio
async def test_write_and_readback(location_client):
    """Write a user location then read back via nearby query."""
    user = {"user_id": "cross-loc-1", "latitude": 25.0173, "longitude": 121.5397}
    r = await location_client.post("/locations", json=user)
    assert r.status_code == 200

    # Query nearby at the same location
    r = await location_client.get(
        "/locations/nearby",
        params={"latitude": 25.0173, "longitude": 121.5397, "radius_meters": 500},
    )
    assert r.status_code == 200
    data = r.json()
    assert "cross-loc-1" in data["users"]


@pytest.mark.asyncio
async def test_write_multiple_users(location_client):
    """Write 5 users then verify all appear in nearby results."""
    base = {"latitude": 25.0173, "longitude": 121.5397}
    for i in range(5):
        uid = f"cross-multi-{i}"
        r = await location_client.post(
            "/locations", json={"user_id": uid, **base}
        )
        assert r.status_code == 200

    r = await location_client.get(
        "/locations/nearby",
        params={"latitude": 25.0173, "longitude": 121.5397, "radius_meters": 500},
    )
    data = r.json()
    for i in range(5):
        assert f"cross-multi-{i}" in data["users"]


@pytest.mark.asyncio
async def test_write_then_move(location_client):
    """User moves far away — should disappear from old nearby query."""
    uid = "cross-move-1"

    # Place at location A
    r = await location_client.post(
        "/locations", json={"user_id": uid, "latitude": 25.0173, "longitude": 121.5397}
    )
    assert r.status_code == 200

    # Query at A — should find user
    r = await location_client.get(
        "/locations/nearby",
        params={"latitude": 25.0173, "longitude": 121.5397, "radius_meters": 500},
    )
    assert uid in r.json()["users"]

    # Move to far location B (Taipei 101 area)
    r = await location_client.post(
        "/locations", json={"user_id": uid, "latitude": 25.0338, "longitude": 121.5645}
    )
    assert r.status_code == 200

    # Query at A again — user should be gone
    r = await location_client.get(
        "/locations/nearby",
        params={"latitude": 25.0173, "longitude": 121.5397, "radius_meters": 500},
    )
    assert uid not in r.json()["users"]


@pytest.mark.asyncio
async def test_concurrent_writes(location_client):
    """10 concurrent writes should all succeed."""
    import asyncio

    async def write_one(i: int):
        return await location_client.post(
            "/locations",
            json={
                "user_id": f"cross-conc-{i}",
                "latitude": 25.0173 + i * 0.0001,
                "longitude": 121.5397,
            },
        )

    results = await asyncio.gather(*[write_one(i) for i in range(10)])
    for r in results:
        assert r.status_code == 200
