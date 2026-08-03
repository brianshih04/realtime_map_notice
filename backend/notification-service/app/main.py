import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from backend.shared.config import DEFAULT_ALERT_RADIUS_METERS, USER_LOCATION_KEY
from backend.shared.cors import configure_cors
from backend.shared.redis_client import create_redis
from backend.shared.schemas import EventNotification, NearbyBroadcast

app = FastAPI(title="realtime_map_notice Notification Service", version="0.1.0")
configure_cors(app)
redis = create_redis()

# WebSocket heartbeat settings
HEARTBEAT_INTERVAL = 30  # seconds
HEARTBEAT_TIMEOUT = 60  # seconds


def user_channel(user_id: str) -> str:
    return f"realtime_map_notice:user:{user_id}:notifications"


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    await redis.ping()
    return {"status": "ok"}


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str) -> None:
    await websocket.accept()
    # 階段一檢核機制：連線時發送 Hello 訊息
    await websocket.send_text('{"type":"hello","message":"Hello"}')
    pubsub = redis.pubsub()
    await pubsub.subscribe(user_channel(user_id))

    ping_task = asyncio.create_task(ping_sender(websocket))

    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0,
            )

            if message and message["type"] == "message":
                await websocket.send_text(message["data"])

            # Check for client messages (pong response)
            try:
                client_msg = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=0.1,
                )
                # Client responded, connection is alive
            except asyncio.TimeoutError:
                pass  # No client message, continue loop

    except WebSocketDisconnect:
        pass
    finally:
        ping_task.cancel()
        await pubsub.unsubscribe(user_channel(user_id))
        await pubsub.close()


async def ping_sender(websocket: WebSocket) -> None:
    """Send periodic ping messages to detect dead connections."""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            try:
                await websocket.send_text('{"type":"ping"}')
            except Exception:
                # WebSocket already closed
                break
    except asyncio.CancelledError:
        pass


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


@app.post("/broadcast/nearby")
async def broadcast_to_nearby_users(broadcast: NearbyBroadcast) -> dict[str, object]:
    """
    階段三：成員C實作的廣播邏輯
    當 Event Service 收到新事件時，呼叫此 endpoint 進行區域推播

    流程：
    1. 使用 Redis GEOSEARCH 查詢指定座標 radius_meters 內的使用者
    2. 對每個附近使用者透過 Redis Pub/Sub 發布通知
    3. 回傳推播結果統計
    """
    # 1. 查詢附近使用者（Redis GEOSEARCH）
    nearby_users = await redis.geosearch(
        USER_LOCATION_KEY,
        longitude=broadcast.longitude,
        latitude=broadcast.latitude,
        radius=broadcast.radius_meters,
        unit="m",
        withdist=True,  # 回傳距離資訊用於除錯
    )

    # 2. 批次推播給附近使用者
    delivered_to: list[dict[str, str | float]] = []
    failed_count = 0

    for user_id, distance in nearby_users:
        notification = EventNotification(
            event_id=broadcast.event_id,
            title=broadcast.title,
            message=broadcast.message,
            latitude=broadcast.latitude,
            longitude=broadcast.longitude,
            severity=broadcast.severity,
            distance_meters=float(distance),
            image_base64=broadcast.image_base64,
        )

        # 透過 Redis Pub/Sub 發布（非阻塞，不需等待 WebSocket 回應）
        subscriber_count = await redis.publish(
            user_channel(user_id),
            notification.model_dump_json(),
        )

        if subscriber_count > 0:
            delivered_to.append({
                "user_id": user_id,
                "distance_meters": float(distance),
                "subscriber_count": subscriber_count,
            })
        else:
            # 使用者目前沒有 WebSocket 連線
            failed_count += 1

    return {
        "event_id": broadcast.event_id,
        "total_nearby_users": len(nearby_users),
        "radius_meters": broadcast.radius_meters,
        "delivered_count": len(delivered_to),
        "failed_count": failed_count,
        "delivered_to": delivered_to[:20],  # 限制回傳數量避免過大
    }
