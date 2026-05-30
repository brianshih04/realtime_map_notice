"""Integration tests for Location Service API.

Uses fakeredis (no real Redis required).
"""

import pytest


class TestHealthz:
    @pytest.mark.asyncio
    async def test_healthz(self, location_client):
        response = await location_client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestUpdateLocation:
    @pytest.mark.asyncio
    async def test_update_location(self, location_client):
        payload = {"user_id": "u-test-1", "latitude": 25.0173, "longitude": 121.5397}
        response = await location_client.post("/locations", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["user_id"] == "u-test-1"

    @pytest.mark.asyncio
    async def test_update_location_twice(self, location_client):
        """Same user_id updated twice — second call succeeds (GEOADD overwrites)."""
        payload = {"user_id": "u-double", "latitude": 25.0173, "longitude": 121.5397}
        r1 = await location_client.post("/locations", json=payload)
        assert r1.status_code == 200

        payload2 = {"user_id": "u-double", "latitude": 25.0180, "longitude": 121.5400}
        r2 = await location_client.post("/locations", json=payload2)
        assert r2.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_latitude(self, location_client):
        response = await location_client.post(
            "/locations",
            json={"user_id": "u-bad", "latitude": 999, "longitude": 121.0},
        )
        assert response.status_code == 422


class TestNearbyUsers:
    @pytest.mark.asyncio
    async def test_get_nearby_users(self, location_client):
        """Place a user then query nearby — should appear in results."""
        await location_client.post(
            "/locations",
            json={"user_id": "u-near-1", "latitude": 25.0173, "longitude": 121.5397},
        )
        response = await location_client.get(
            "/locations/nearby",
            params={"latitude": 25.0173, "longitude": 121.5397, "radius_meters": 500},
        )
        assert response.status_code == 200
        data = response.json()
        assert "u-near-1" in data["users"]

    @pytest.mark.asyncio
    async def test_get_nearby_users_no_result(self, location_client):
        """Query a location far from any placed user."""
        await location_client.post(
            "/locations",
            json={"user_id": "u-far", "latitude": 25.0173, "longitude": 121.5397},
        )
        response = await location_client.get(
            "/locations/nearby",
            params={"latitude": 35.6762, "longitude": 139.6503, "radius_meters": 500},
        )
        assert response.status_code == 200
        data = response.json()
        assert "u-far" not in data["users"]

    @pytest.mark.asyncio
    async def test_get_nearby_default_radius(self, location_client):
        """Default radius should be 500m."""
        response = await location_client.get(
            "/locations/nearby",
            params={"latitude": 25.0, "longitude": 121.0},
        )
        # Should work with default
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_nearby_out_of_range(self, location_client):
        """Query parameters with latitude out of range still returns 200
        (FastAPI validates query float type, not range — range validation
        is on POST body only)."""
        response = await location_client.get(
            "/locations/nearby",
            params={"latitude": 91, "longitude": 121.0},
        )
        # FastAPI allows any float query param; the GEOSEARCH just returns empty
        assert response.status_code == 200
        assert response.json() == {"users": []}
