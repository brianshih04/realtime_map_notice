"""Cross-service test: Event Service → Notification Service HTTP calls.

Requires: docker compose up -d
"""

import pytest


@pytest.mark.asyncio
async def test_event_triggers_notification(location_client, event_client):
    """Write a user, create event, verify delivered_count >= 1."""
    uid = "cross-event-nearby"
    r = await location_client.post(
        "/locations",
        json={"user_id": uid, "latitude": 25.0173, "longitude": 121.5397},
    )
    assert r.status_code == 200

    r = await event_client.post(
        "/events",
        json={
            "title": "Cross-service test",
            "message": "Notification should fire",
            "latitude": 25.0173,
            "longitude": 121.5397,
            "severity": "info",
            "radius_meters": 200,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["delivered_count"] >= 1
    assert uid in data["delivered_to"]


@pytest.mark.asyncio
async def test_event_no_nearby_users(event_client):
    """Create event in empty location — delivered_count should be 0."""
    r = await event_client.post(
        "/events",
        json={
            "title": "Nobody here",
            "message": "Should deliver to 0",
            "latitude": 25.0173,
            "longitude": 121.5397,
            "severity": "info",
            "radius_meters": 100,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["nearby_user_count"] == 0
    assert data["delivered_count"] == 0


@pytest.mark.asyncio
async def test_event_multiple_recipients(location_client, event_client):
    """10 users nearby — all should receive notification."""
    for i in range(10):
        uid = f"cross-multi-rcpt-{i}"
        r = await location_client.post(
            "/locations",
            json={
                "user_id": uid,
                "latitude": 25.0173 + i * 0.0005,
                "longitude": 121.5397,
            },
        )
        assert r.status_code == 200

    r = await event_client.post(
        "/events",
        json={
            "title": "Mass notify",
            "message": "Everyone nearby",
            "latitude": 25.0173,
            "longitude": 121.5397,
            "severity": "info",
            "radius_meters": 1000,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["delivered_count"] == data["nearby_user_count"]


@pytest.mark.asyncio
async def test_event_notification_payload(location_client, event_client):
    """Event service response should have correct structure."""
    uid = "cross-payload"
    await location_client.post(
        "/locations",
        json={"user_id": uid, "latitude": 25.0173, "longitude": 121.5397},
    )

    r = await event_client.post(
        "/events",
        json={
            "title": "Payload check",
            "message": "Verify structure",
            "latitude": 25.0173,
            "longitude": 121.5397,
            "severity": "urgent",
            "radius_meters": 500,
        },
    )
    data = r.json()
    assert "event_id" in data
    assert "nearby_user_count" in data
    assert "delivered_count" in data
    assert "delivered_to" in data
