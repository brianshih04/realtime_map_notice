from datetime import UTC, datetime

from fastapi import FastAPI

from backend.shared.config import LAST_SEEN_TTL_SECONDS, USER_LAST_SEEN_PREFIX, USER_LOCATION_KEY
from backend.shared.cors import configure_cors
from backend.shared.redis_client import create_redis
from backend.shared.schemas import LocationUpdate

app = FastAPI(title="realtime_map_notice Location Service", version="0.1.0")
configure_cors(app)
redis = create_redis()


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    await redis.ping()
    return {"status": "ok"}


@app.post("/locations")
async def update_location(payload: LocationUpdate) -> dict[str, str]:
    await redis.geoadd(
        USER_LOCATION_KEY,
        (payload.longitude, payload.latitude, payload.user_id),
    )
    await redis.set(
        f"{USER_LAST_SEEN_PREFIX}:{payload.user_id}",
        datetime.now(UTC).isoformat(),
        ex=LAST_SEEN_TTL_SECONDS,
    )
    return {"status": "accepted", "user_id": payload.user_id}


@app.get("/locations/nearby")
async def nearby_users(
    latitude: float,
    longitude: float,
    radius_meters: int = 500,
) -> dict[str, list[str]]:
    users = await redis.geosearch(
        USER_LOCATION_KEY,
        longitude=longitude,
        latitude=latitude,
        radius=radius_meters,
        unit="m",
    )
    return {"users": users}
