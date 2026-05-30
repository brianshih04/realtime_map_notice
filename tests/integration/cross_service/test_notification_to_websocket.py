"""Cross-service test: Notification Service → WebSocket delivery.

Requires: docker compose up -d
Uses the `websockets` library for WS client testing.
"""

import asyncio
import json

import pytest
from websockets import connect as ws_connect


@pytest.mark.asyncio
async def test_notify_connected_client(notification_url, notification_client):
    """Connect WebSocket, publish notification, verify receipt."""
    ws_url = notification_url.replace("http://", "ws://")
    user_id = "cross-ws-rcv"

    async with ws_connect(f"{ws_url}/ws/{user_id}") as ws:
        # Small delay to ensure subscription is active
        await asyncio.sleep(0.5)

        # Send notification via REST API
        from backend.shared.schemas import EventNotification

        payload = EventNotification(
            event_id="evt-cross-ws",
            title="WS Notification",
            message="Via cross-service test",
            latitude=25.0173,
            longitude=121.5397,
            severity="info",
            distance_meters=100.0,
        )

        import httpx

        async with httpx.AsyncClient(base_url=notification_url, timeout=5.0) as client:
            r = await client.post(
                f"/notify/{user_id}", json=payload.model_dump()
            )
            assert r.status_code == 200
            assert r.json()["status"] == "published"

        # Receive on WebSocket
        try:
            data = await asyncio.wait_for(ws.recv(), timeout=3.0)
            parsed = json.loads(data)
            assert parsed.get("event_id") == "evt-cross-ws"
            assert parsed.get("title") == "WS Notification"
        except asyncio.TimeoutError:
            pytest.fail("Timed out waiting for WebSocket message")


@pytest.mark.asyncio
async def test_notify_unconnected_client(notification_client):
    """Notify a user with no WebSocket — subscriber_count should be 0."""
    from backend.shared.schemas import EventNotification

    payload = EventNotification(
        event_id="evt-no-ws",
        title="No WS",
        message="Nobody listening",
        latitude=25.0,
        longitude=121.0,
        severity="info",
        distance_meters=None,
    )

    r = await notification_client.post(
        "/notify/u-no-websocket", json=payload.model_dump()
    )
    assert r.status_code == 200
    data = r.json()
    assert data["subscriber_count"] == 0
    assert data["status"] == "published"


@pytest.mark.asyncio
async def test_multi_websocket_no_cross_talk(notification_url):
    """Two WebSocket connections — each only receives its own notifications."""
    ws_url = notification_url.replace("http://", "ws://")

    user_a = "cross-ws-a"
    user_b = "cross-ws-b"

    import httpx

    async with (
        ws_connect(f"{ws_url}/ws/{user_a}") as ws_a,
        ws_connect(f"{ws_url}/ws/{user_b}") as ws_b,
    ):
        await asyncio.sleep(0.5)

        # Notify user A only
        from backend.shared.schemas import EventNotification

        payload_a = EventNotification(
            event_id="evt-for-a",
            title="Only for A",
            message="A's message",
            latitude=25.0,
            longitude=121.0,
            severity="info",
        )

        async with httpx.AsyncClient(base_url=notification_url, timeout=5.0) as client:
            await client.post(f"/notify/{user_a}", json=payload_a.model_dump())

        # A should receive
        try:
            msg_a = await asyncio.wait_for(ws_a.recv(), timeout=3.0)
            assert "evt-for-a" in msg_a
        except asyncio.TimeoutError:
            pytest.fail("User A did not receive notification")

        # B should NOT receive
        try:
            msg_b = await asyncio.wait_for(ws_b.recv(), timeout=2.0)
            # If B got something, ensure it's not A's notification
            parsed = json.loads(msg_b)
            assert parsed.get("event_id") != "evt-for-a"
        except asyncio.TimeoutError:
            # Expected — B received nothing
            pass
