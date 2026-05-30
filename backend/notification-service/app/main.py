import asyncio
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from backend.shared.cors import configure_cors
from backend.shared.redis_client import create_redis
from backend.shared.schemas import EventNotification

HEARTBEAT_INTERVAL = 30  # seconds
RECEIVE_TIMEOUT = 10  # seconds — shorter than heartbeat to detect dead clients

app = FastAPI(title="realtime_map_notice Notification Service", version="0.1.0")
configure_cors(app)
redis = create_redis()


def user_channel(user_id: str) -> str:
    return f"realtime_map_notice:user:{user_id}:notifications"


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    await redis.ping()
    return {"status": "ok"}


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str) -> None:
    await websocket.accept()
    pubsub = redis.pubsub()
    await pubsub.subscribe(user_channel(user_id))

    conn_id = str(uuid4())[:8]

    async def heartbeat_loop() -> None:
        """Periodically send ping frames to detect dead connections."""
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await websocket.send_json({"type": "ping", "conn_id": conn_id})
            except Exception:
                break

    heartbeat_task = asyncio.create_task(heartbeat_loop())

    try:
        while True:
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    ),
                    timeout=RECEIVE_TIMEOUT,
                )
                if message and message["type"] == "message":
                    await websocket.send_text(message["data"])
            except asyncio.TimeoutError:
                # No pubsub message received within timeout — check client is still alive
                try:
                    await websocket.send_json({"type": "ping", "conn_id": conn_id})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        await pubsub.unsubscribe(user_channel(user_id))
        await pubsub.close()


@app.post("/notify/{user_id}")
async def notify_user(user_id: str, notification: EventNotification) -> dict[str, object]:
    subscriber_count = await redis.publish(
        user_channel(user_id),
        notification.model_dump_json(),
    )
    return {
        "user_id": user_id,
        "subscriber_count": subscriber_count,
        "status": "published",
    }
