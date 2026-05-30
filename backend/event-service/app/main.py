import asyncio
import os
from uuid import uuid4

import httpx
from fastapi import FastAPI

from backend.shared.config import USER_LOCATION_KEY
from backend.shared.cors import configure_cors
from backend.shared.redis_client import create_redis
from backend.shared.schemas import EventCreate, EventNotification

NOTIFICATION_SERVICE_URL = os.getenv(
    "NOTIFICATION_SERVICE_URL",
    "http://localhost:8003",
)

# TTL for idempotency keys — prevents duplicate event delivery within this window
EVENT_IDEMPOTENCY_TTL = int(os.getenv("EVENT_IDEMPOTENCY_TTL", "300"))

app = FastAPI(title="realtime_map_notice Event Service", version="0.1.0")
configure_cors(app)
redis = create_redis()


async def _notify_user(
    client: httpx.AsyncClient,
    user_id: str,
    notification: EventNotification,
) -> str | None:
    """Notify a single user. Returns user_id on success, None on failure."""
    try:
        response = await client.post(
            f"{NOTIFICATION_SERVICE_URL}/notify/{user_id}",
            json=notification.model_dump(),
            timeout=3.0,
        )
        if response.status_code < 400:
            return user_id
    except httpx.HTTPError:
        pass
    return None


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    await redis.ping()
    return {"status": "ok"}


@app.post("/events")
async def create_event(payload: EventCreate) -> dict[str, object]:
    event_id = str(uuid4())

    # Idempotency: claim this event_id to prevent duplicate processing
    # across multiple replicas (K8s multi-replica safety)
    idempotency_key = f"realtime_map_notice:event:processed:{event_id}"
    claimed = await redis.set(idempotency_key, "1", nx=True, ex=EVENT_IDEMPOTENCY_TTL)
    if not claimed:
        return {
            "event_id": event_id,
            "status": "duplicate",
            "detail": "This event was already processed by another replica.",
        }

    nearby_users = await redis.geosearch(
        USER_LOCATION_KEY,
        longitude=payload.longitude,
        latitude=payload.latitude,
        radius=payload.radius_meters,
        unit="m",
        withdist=True,
    )

    if not nearby_users:
        return {
            "event_id": event_id,
            "nearby_user_count": 0,
            "delivered_count": 0,
            "delivered_to": [],
        }

    # Build notifications per user
    user_notifications: list[tuple[str, EventNotification]] = []
    for user_id, distance in nearby_users:
        notification = EventNotification(
            event_id=event_id,
            title=payload.title,
            message=payload.message,
            latitude=payload.latitude,
            longitude=payload.longitude,
            severity=payload.severity,
            distance_meters=float(distance),
        )
        user_notifications.append((user_id, notification))

    # Send all notifications concurrently
    async with httpx.AsyncClient() as client:
        tasks = [
            _notify_user(client, user_id, notification)
            for user_id, notification in user_notifications
        ]
        results = await asyncio.gather(*tasks)

    delivered_to: list[str] = [uid for uid in results if uid is not None]

    return {
        "event_id": event_id,
        "nearby_user_count": len(nearby_users),
        "delivered_count": len(delivered_to),
        "delivered_to": delivered_to[:20],
    }
