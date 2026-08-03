import json
import os
from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

import asyncio
import httpx
from fastapi import FastAPI, Query

from backend.shared.config import USER_LAST_SEEN_PREFIX, USER_LOCATION_KEY
from backend.shared.cors import configure_cors
from backend.shared.redis_client import create_redis
from backend.shared.schemas import EventCreate, EventNotification,EventResponse

NOTIFICATION_SERVICE_URL = os.getenv(
    "NOTIFICATION_SERVICE_URL",
    "http://localhost:8003",
)

EVENT_LOCATION_KEY = "event_locations"

app = FastAPI(title="realtime_map_notice Event Service", version="0.1.0")
configure_cors(app)
redis = create_redis()


async def get_active_users(nearby_users: Sequence[tuple[str, str]]) -> list[tuple[str, float]]:
    if not nearby_users:
        return []

    pipe = redis.pipeline(transaction=False)
    for user_id, _ in nearby_users:
        pipe.get(f"{USER_LAST_SEEN_PREFIX}:{user_id}")

    last_seen_values = await pipe.execute()

    active_users: list[tuple[str, float]] = []
    for (user_id, distance), last_seen in zip(nearby_users, last_seen_values):
        if last_seen:
            active_users.append((user_id, float(distance)))

    return active_users


async def deliver_notification(
    client: httpx.AsyncClient,
    user_id: str,
    notification: EventNotification,
) -> bool:
    try:
        response = await client.post(
            f"{NOTIFICATION_SERVICE_URL}/notify/{user_id}",
            json=notification.model_dump(),
        )
    except httpx.HTTPError:
        return False

    return response.status_code < 400


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    await redis.ping()
    return {"status": "ok"}

@app.get("/events", response_model=list[EventResponse])
async def get_events(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius: int = Query(3000, ge=1),
):
    event_ids = await redis.geosearch(
        EVENT_LOCATION_KEY,
        longitude=longitude,
        latitude=latitude,
        radius=radius,
        unit="m",
    )

    if not event_ids:
        return []

    pipe = redis.pipeline(transaction=False)

    for event_id in event_ids:
        pipe.get(f"event:{event_id}")

    event_data_list = await pipe.execute()

    events = []
    expired_events = []

    for event_id, event_data in zip(event_ids, event_data_list):
        # Redis TTL 到期，event 不存在
        if event_data is None:
            expired_events.append(event_id)
            continue

        event = json.loads(event_data)

        events.append(
            EventResponse(
                event_id=event_id,
                title=event["title"],
                message=event["message"],
                severity=event["severity"],
                latitude=event["latitude"],
                longitude=event["longitude"],
                radius_meters=event["radius_meters"],
                created_at=event["created_at"],
            )
        )

    # 清掉已過期的 GEO 資料
    if expired_events:
        await redis.zrem(
            EVENT_LOCATION_KEY,
            *expired_events,
        )

    return events

@app.post("/events")
async def create_event(payload: EventCreate) -> dict[str, object]:
    event_id = str(uuid4())

    event_data = payload.model_dump()
    event_data["created_at"] = datetime.now(timezone.utc).isoformat()

    await redis.set(
        f"event:{event_id}",
        json.dumps(event_data),
        ex=payload.duration_minutes * 60,
    )

    await redis.geoadd(
        EVENT_LOCATION_KEY,
        (
            payload.longitude,
            payload.latitude,
            event_id,
        ),
    )

    nearby_users = await redis.geosearch(
        USER_LOCATION_KEY,
        longitude=payload.longitude,
        latitude=payload.latitude,
        radius=payload.radius_meters,
        unit="m",
        withdist=True,
    )
    active_users = await get_active_users(nearby_users)

    delivered_to: list[str] = []
    async with httpx.AsyncClient(timeout=3.0) as client:
        tasks = []
        for user_id, distance in active_users:
            notification = EventNotification(
                event_id=event_id,
                title=payload.title,
                message=payload.message,
                latitude=payload.latitude,
                longitude=payload.longitude,
                severity=payload.severity,
                distance_meters=float(distance),
                image_base64=payload.image_base64,
            )
            tasks.append(deliver_notification(client, user_id, notification))

        results = await asyncio.gather(*tasks) if tasks else []
        for (user_id, _), success in zip(active_users, results):
            if success:
                delivered_to.append(user_id)

    return {
        "event_id": event_id,
        "nearby_user_count": len(nearby_users),
        "active_user_count": len(active_users),
        "delivered_count": len(delivered_to),
        "delivered_to": delivered_to[:20],
    }
