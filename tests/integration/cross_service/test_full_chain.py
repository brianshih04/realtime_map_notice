"""Full chain integration test — simulates the complete demo flow.

Requires: docker compose up -d

Flow:
1. Upload user_A and user_B locations (within 500m of each other)
2. Verify both appear in nearby query
3. user_A and user_B connect via WebSocket
4. Create an urgent event between them
5. Both receive the notification via WebSocket
6. Upload user_C far away (>1000m)
7. user_C connects WebSocket
8. Create another event
9. user_C does NOT receive notification
"""

import asyncio
import json

import httpx
import pytest
from websockets import connect as ws_connect


@pytest.mark.asyncio
async def test_demo_full_flow(location_url, event_url, notification_url):
    """Complete end-to-end demo simulation."""
    ws_url = notification_url.replace("http://", "ws://")

    user_a = "demo-user-a"
    user_b = "demo-user-b"
    user_c = "demo-user-c"

    async with httpx.AsyncClient(base_url=location_url, timeout=5.0) as loc:
        async with httpx.AsyncClient(base_url=event_url, timeout=5.0) as evt:

            # Step 1: Upload user_A and user_B (close to each other)
            for uid, lat, lng in [
                (user_a, 25.0173, 121.5397),
                (user_b, 25.0185, 121.5405),
                (user_c, 25.0500, 121.5600),  # far away
            ]:
                r = await loc.post(
                    "/locations",
                    json={"user_id": uid, "latitude": lat, "longitude": lng},
                )
                assert r.status_code == 200, f"Failed to upload {uid}"

            # Step 2: Verify A and B are nearby, C is not
            r = await loc.get(
                "/locations/nearby",
                params={
                    "latitude": 25.0179,
                    "longitude": 121.5400,
                    "radius_meters": 500,
                },
            )
            nearby = r.json()["users"]
            assert user_a in nearby
            assert user_b in nearby
            assert user_c not in nearby

            # Step 3: Connect A and B via WebSocket
            async with (
                ws_connect(f"{ws_url}/ws/{user_a}") as ws_a,
                ws_connect(f"{ws_url}/ws/{user_b}") as ws_b,
            ):
                await asyncio.sleep(0.5)  # Wait for subscriptions

                # Step 4: Create event near A and B
                r = await evt.post(
                    "/events",
                    json={
                        "title": "Demo Event",
                        "message": "This is a full chain test",
                        "latitude": 25.0179,
                        "longitude": 121.5400,
                        "severity": "urgent",
                        "radius_meters": 500,
                    },
                )
                assert r.status_code == 200
                event_data = r.json()
                assert event_data["delivered_count"] >= 2, (
                    f"Expected >=2 deliveries, got {event_data['delivered_count']}"
                )

                # Step 5: Both A and B receive the notification
                for label, ws in [("A", ws_a), ("B", ws_b)]:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                        parsed = json.loads(msg)
                        # May be a ping, skip
                        if parsed.get("type") == "ping":
                            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                            parsed = json.loads(msg)
                        assert parsed.get("event_id") == event_data["event_id"], (
                            f"User {label} received wrong event_id"
                        )
                    except asyncio.TimeoutError:
                        pytest.fail(
                            f"User {label} did not receive notification within timeout"
                        )

            # Step 6-9: Verify user C does NOT receive
            async with ws_connect(f"{ws_url}/ws/{user_c}") as ws_c:
                await asyncio.sleep(0.5)

                r = await evt.post(
                    "/events",
                    json={
                        "title": "C should NOT receive this",
                        "message": "Far away event",
                        "latitude": 25.0179,
                        "longitude": 121.5400,
                        "severity": "info",
                        "radius_meters": 200,
                    },
                )
                assert r.status_code == 200

                try:
                    msg = await asyncio.wait_for(ws_c.recv(), timeout=3.0)
                    # If we got a ping, ignore it
                    parsed = json.loads(msg)
                    if parsed.get("type") == "ping":
                        # Try again
                        msg = await asyncio.wait_for(ws_c.recv(), timeout=2.0)
                        parsed = json.loads(msg)
                    # Should only get pings, not event notifications
                    if parsed.get("event_id"):
                        pytest.fail(
                            f"User C incorrectly received notification: {parsed}"
                        )
                except asyncio.TimeoutError:
                    # Expected — C should NOT receive anything
                    pass
