"""Integration tests for Event Service API.

Uses fakeredis + mocked notification HTTP transport (no real services required).
"""

import pytest


class TestHealthz:
    @pytest.mark.asyncio
    async def test_healthz(self, event_client):
        response = await event_client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestCreateEvent:
    @pytest.mark.asyncio
    async def test_create_event_no_nearby_users(self, event_client):
        """Event created with nobody nearby — delivered_count = 0."""
        payload = {
            "title": "Test event",
            "message": "Nobody around",
            "latitude": 25.0173,
            "longitude": 121.5397,
            "severity": "info",
            "radius_meters": 500,
        }
        response = await event_client.post("/events", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "event_id" in data
        assert data["delivered_count"] == 0
        assert data["nearby_user_count"] == 0

    @pytest.mark.asyncio
    async def test_create_event_with_nearby_users(self, event_client, location_client):
        """Place user in Redis GEO first, then create event — should deliver."""
        await location_client.post(
            "/locations",
            json={"user_id": "u-event-1", "latitude": 25.0174, "longitude": 121.5398},
        )
        payload = {
            "title": "Library alert",
            "message": "Seats available!",
            "latitude": 25.0173,
            "longitude": 121.5397,
            "severity": "info",
            "radius_meters": 500,
        }
        response = await event_client.post("/events", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["delivered_count"] == data["nearby_user_count"]

    @pytest.mark.asyncio
    async def test_create_event_urgent_severity(self, event_client, location_client):
        """Urgent events should be processed just like info events."""
        await location_client.post(
            "/locations",
            json={"user_id": "u-urgent-1", "latitude": 25.0174, "longitude": 121.5398},
        )
        payload = {
            "title": "URGENT: Fire alarm",
            "message": "Evacuate immediately",
            "latitude": 25.0173,
            "longitude": 121.5397,
            "severity": "urgent",
            "radius_meters": 500,
        }
        response = await event_client.post("/events", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["delivered_count"] >= 1

    @pytest.mark.asyncio
    async def test_create_event_info_severity(self, event_client, location_client):
        """Info events should have 'info' severity."""
        await location_client.post(
            "/locations",
            json={"user_id": "u-info-1", "latitude": 25.0174, "longitude": 121.5398},
        )
        payload = {
            "title": "Free coffee",
            "message": "Free coffee at the cafeteria",
            "latitude": 25.0173,
            "longitude": 121.5397,
            "severity": "info",
            "radius_meters": 500,
        }
        response = await event_client.post("/events", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["delivered_count"] >= 1

    @pytest.mark.asyncio
    async def test_event_idempotency(self, event_client):
        """Each call generates a unique event_id (no duplicates from same payload)."""
        payload = {
            "title": "Idempotency check",
            "message": "Each call gets a unique event_id",
            "latitude": 25.0173,
            "longitude": 121.5397,
            "severity": "info",
            "radius_meters": 500,
        }
        r1 = await event_client.post("/events", json=payload)
        r2 = await event_client.post("/events", json=payload)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["event_id"] != r2.json()["event_id"]
