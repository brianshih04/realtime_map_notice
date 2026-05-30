"""Integration tests for Notification Service REST API + WebSocket Pub/Sub.

Uses fakeredis for pub/sub.
"""

import asyncio
import pytest


class TestHealthz:
    @pytest.mark.asyncio
    async def test_healthz(self, notification_client):
        response = await notification_client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestNotifyUser:
    @pytest.mark.asyncio
    async def test_notify_user_no_subscribers(self, notification_client):
        """Notify a user with no active WebSocket — subscriber_count = 0."""
        from backend.shared.schemas import EventNotification

        notification = EventNotification(
            event_id="evt-test-1",
            title="Test",
            message="Hello",
            latitude=25.0,
            longitude=121.0,
            severity="info",
            distance_meters=100.0,
        )
        response = await notification_client.post(
            "/notify/u-no-ws",
            json=notification.model_dump(),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "u-no-ws"
        assert data["subscriber_count"] == 0
        assert data["status"] == "published"


class TestPubSub:
    @pytest.mark.asyncio
    async def test_pubsub_delivery(self):
        """Publish a message to a subscribed channel — verify receipt."""
        from fakeredis import FakeAsyncRedis

        redis = FakeAsyncRedis()
        channel = "realtime_map_notice:user:u-test:notifications"

        # Subscribe first
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)

        # Give subscription a moment
        await asyncio.sleep(0.05)

        # Publish
        payload = '{"event_id":"evt-1","title":"Hello"}'
        count = await redis.publish(channel, payload)
        assert count == 1

        # Receive — poll since fakeredis get_message may not block
        msg = None
        for _ in range(10):
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
            if msg and msg["type"] == "message":
                break
            await asyncio.sleep(0.05)

        assert msg is not None, "Should have received a message"
        assert msg["type"] == "message"
        # fakeredis may return bytes data; handle both
        data = msg["data"]
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        assert "evt-1" in data

        await pubsub.unsubscribe(channel)

    @pytest.mark.asyncio
    async def test_pubsub_no_subscribers(self):
        """Publishing to a channel with no subscribers returns 0."""
        from fakeredis import FakeAsyncRedis

        redis = FakeAsyncRedis()
        count = await redis.publish(
            "realtime_map_notice:user:u-nobody:notifications",
            '{"event_id":"evt-2"}',
        )
        assert count == 0

    @pytest.mark.asyncio
    async def test_pubsub_no_cross_talk(self):
        """Messages for channel A do not arrive on channel B."""
        from fakeredis import FakeAsyncRedis

        redis = FakeAsyncRedis()

        # Subscribe B
        pubsub_b = redis.pubsub()
        await pubsub_b.subscribe("realtime_map_notice:user:u-b:notifications")
        await asyncio.sleep(0.05)

        # Publish to A
        await redis.publish(
            "realtime_map_notice:user:u-a:notifications",
            '{"event_id":"evt-a"}',
        )

        # B should not receive anything
        msg = await pubsub_b.get_message(ignore_subscribe_messages=True, timeout=0.2)
        assert msg is None, f"User B should not receive A's message, got: {msg}"

        await pubsub_b.unsubscribe("realtime_map_notice:user:u-b:notifications")
