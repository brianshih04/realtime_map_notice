import asyncio
import json
import logging

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from redis.exceptions import RedisError

from backend.shared.config import DEFAULT_ALERT_RADIUS_METERS, USER_LAST_SEEN_PREFIX, USER_LOCATION_KEY
from backend.shared.cors import configure_cors
from backend.shared.redis_client import create_redis
from backend.shared import push
from backend.shared.schemas import EventNotification, NearbyBroadcast, PushSubscription

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="realtime_map_notice Notification Service", version="0.1.0")
configure_cors(app)
redis = create_redis()

# WebSocket heartbeat settings
HEARTBEAT_INTERVAL = 30  # seconds
HEARTBEAT_TIMEOUT = 60  # seconds
PONG_TIMEOUT = 10  # seconds - wait for pong response
INITIAL_GRACE_PERIOD = 60  # seconds - grace period after connection establishment


def user_channel(user_id: str) -> str:
    return f"realtime_map_notice:user:{user_id}:notifications"


# 全域控制頻道：ops 儀表板清空事件時 publish 到這裡，所有 WS 連線收到後
# 立即清空前端地圖，不必等前端的 15 秒定期同步
OPS_RESET_CHANNEL = "realtime_map_notice:ops:reset"


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    await redis.ping()
    return {"status": "ok"}


@app.get("/push/public-key")
async def get_push_public_key() -> dict[str, object]:
    return {
        "public_key": push.VAPID_PUBLIC_KEY or None,
        "configured": push.push_is_configured(),
    }


@app.post("/push-subscriptions/{user_id}")
async def register_push_subscription(
    user_id: str,
    subscription: PushSubscription,
) -> dict[str, str]:
    try:
        await push.register_subscription(
            redis,
            user_id,
            subscription.model_dump(by_alias=True, exclude_none=True),
        )
    except RedisError as e:
        logger.error("Push subscription storage failed: %s", e)
        raise HTTPException(status_code=503, detail="Notification storage unavailable") from e
    return {"status": "registered", "user_id": user_id}


@app.delete("/push-subscriptions/{user_id}")
async def unregister_push_subscription(
    user_id: str,
    subscription: PushSubscription,
) -> dict[str, object]:
    try:
        removed = await push.remove_subscription(
            redis,
            user_id,
            subscription.endpoint,
        )
    except RedisError as e:
        logger.error("Push subscription removal failed: %s", e)
        raise HTTPException(status_code=503, detail="Notification storage unavailable") from e
    return {"status": "removed" if removed else "not_found", "user_id": user_id}


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str) -> None:
    await websocket.accept()
    # 階段一檢核機制：連線時發送 Hello 訊息
    await websocket.send_text('{"type":"hello","message":"Connected to notification service"}')

    logger.info(f"✅ User {user_id} connected, sending hello message")

    pubsub = redis.pubsub()
    await pubsub.subscribe(user_channel(user_id))
    await pubsub.subscribe(OPS_RESET_CHANNEL)

    # 追蹤最後一次收到 pong 的時間
    last_pong_time = asyncio.get_event_loop().time()
    connection_start_time = asyncio.get_event_loop().time()

    # 心跳狀態：記錄最後一次 ping 送出時間，供主迴圈判斷 pong 逾時
    heartbeat: dict = {}
    ping_task = asyncio.create_task(ping_sender(websocket, heartbeat))

    try:
        while True:
            # 1. 檢查是否有 Redis 訊息
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                    timeout=2.0
                )

                if message and message["type"] == "message":
                    channel = message.get("channel")
                    if isinstance(channel, bytes):
                        channel = channel.decode()
                    if channel == OPS_RESET_CHANNEL:
                        # 儀表板清空事件：轉發 reset 指令，前端立即清空地圖
                        await websocket.send_text('{"type":"reset"}')
                    else:
                        await websocket.send_text(message["data"])
                        logger.info(f"📤 Sent notification to user {user_id}")
            except asyncio.TimeoutError:
                pass  # 沒有 Redis 訊息，繼續迴圈

            # 2. 檢查客戶端訊息 (pong response)
            try:
                client_msg = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=0.5,
                )
                # 解析客戶端訊息
                try:
                    msg_data = json.loads(client_msg)
                    if msg_data.get("type") == "pong":
                        last_pong_time = asyncio.get_event_loop().time()
                        logger.info(f"📡 User {user_id} pong received")
                    else:
                        logger.info(f"📨 User {user_id} sent: {client_msg[:50]}...")
                except json.JSONDecodeError:
                    logger.info(f"📨 User {user_id} sent non-JSON: {client_msg[:50]}...")
            except asyncio.TimeoutError:
                pass  # 沒有客戶端訊息，繼續迴圈

            # 3. 檢查 pong 超時：倒數從 ping 實際送出後才開始。
            # （stage 5 修正：舊邏輯從連線建立起算，會在第一個 ping 送出前
            #   就把剛連上 30 秒的健康連線誤殺）
            current_time = asyncio.get_event_loop().time()
            last_ping_sent = heartbeat.get("last_ping_sent")

            if last_ping_sent is not None and last_pong_time < last_ping_sent:
                time_since_ping = current_time - last_ping_sent
                if time_since_ping > PONG_TIMEOUT:
                    logger.warning(f"⏰ User {user_id} pong timeout ({time_since_ping:.1f}s > {PONG_TIMEOUT}s), closing connection")
                    break

            # 每 60 秒打印一次連線狀態
            connection_age = current_time - connection_start_time
            if int(connection_age) % 60 == 0 and int(connection_age) > 0:
                logger.info(f"💓 User {user_id} connection alive for {int(connection_age)}s")

    except WebSocketDisconnect:
        logger.info(f"🔌 User {user_id} disconnected normally")
    except Exception as e:
        logger.error(f"❌ WebSocket error for user {user_id}: {e}")
    finally:
        ping_task.cancel()
        await pubsub.unsubscribe(user_channel(user_id))
        await pubsub.unsubscribe(OPS_RESET_CHANNEL)
        await pubsub.close()
        logger.info(f"🛑 User {user_id} connection cleanup complete")


async def ping_sender(websocket: WebSocket, heartbeat: dict) -> None:
    """Send periodic ping messages; the main loop times the pong window from these send times."""
    try:
        # 等待第一個心跳間隔後才發送第一次 ping
        await asyncio.sleep(HEARTBEAT_INTERVAL)

        try:
            heartbeat["last_ping_sent"] = asyncio.get_event_loop().time()
            await websocket.send_text('{"type":"ping","timestamp":' + str(int(asyncio.get_event_loop().time())) + '}')
        except Exception:
            # WebSocket already closed
            print("Ping failed: connection closed")
            return

        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            try:
                heartbeat["last_ping_sent"] = asyncio.get_event_loop().time()
                await websocket.send_text('{"type":"ping","timestamp":' + str(int(asyncio.get_event_loop().time())) + '}')
            except Exception:
                # WebSocket already closed
                print("Ping failed: connection closed")
                break
    except asyncio.CancelledError:
        pass


@app.post("/notify/{user_id}")
async def notify_user(user_id: str, notification: EventNotification) -> dict[str, object]:
    if notification.deep_link is None:
        notification = notification.model_copy(
            update={"deep_link": f"event:{notification.event_id}"}
        )

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
    Stage 5 起為唯一正式推播路徑：Event Service 收到新事件後只需呼叫本
    endpoint 一次，GEO 比對、離線過濾與批次發布全部由 Notification Service 負責。

    流程：
    1. 使用 Redis GEOSEARCH 查詢指定座標 radius_meters 內的使用者
    2. 以 last_seen key 的 TTL 過濾離線使用者（過期即淘汰）
    3. 用 Redis pipeline 批次發布通知（取代逐一 await，人群密集時延遲更穩定）
    4. 回傳推播結果統計
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

    # 2. 依 last_seen 分流：
    #    在線使用者 → WebSocket＋系統推播；
    #    離線但已訂閱推播的使用者 → 僅送系統推播（用最後已知位置，
    #    這是 Web Push「沒開 App 也收得到」的核心價值）
    pipe = redis.pipeline(transaction=False)
    for uid, _ in nearby_users:
        pipe.get(f"{USER_LAST_SEEN_PREFIX}:{uid}")

    last_seen_values = await pipe.execute()
    active_users = []
    offline_push_users = []
    for (uid, distance), last_seen in zip(nearby_users, last_seen_values):
        if last_seen:
            active_users.append((uid, float(distance)))
        elif await push.has_subscriptions(redis, uid):
            offline_push_users.append((uid, float(distance)))

    # 3. pipeline 批次發布：每位使用者的通知帶各自距離，一次送出全部 publish
    def build_notification(distance: float) -> EventNotification:
        return EventNotification(
            event_id=broadcast.event_id,
            user_id=broadcast.user_id,
            title=broadcast.title,
            message=broadcast.message,
            latitude=broadcast.latitude,
            longitude=broadcast.longitude,
            severity=broadcast.severity,
            distance_meters=distance,
            duration_minutes=broadcast.duration_minutes,
            created_at=broadcast.created_at,
            expires_at=broadcast.expires_at,
            deep_link=f"event:{broadcast.event_id}",
            location_label=broadcast.location_label,
            image_base64=broadcast.image_base64,
            image_url=broadcast.image_url,
            analysis=broadcast.analysis,
        )

    def build_push_payload(distance: float) -> dict:
        """Web Push 之傳輸負載上限為 4096 bytes（RFC 8291 加密前明文上限），
        照片等大型欄位一律剝離——通知橫幅（sw.js）僅使用標題、訊息、距離與
        地標欄位；照片由前端點開通知後經 GET /events 取得。未剝離前，帶圖
        事件之推播必被推播伺服器以 413 拒收，造成「有圖的事件收不到通知」。
        """
        slim = build_notification(distance).model_dump(mode="json")
        slim.pop("image_base64", None)
        slim.pop("image_url", None)
        slim.pop("analysis", None)
        return slim

    pipe = redis.pipeline(transaction=False)
    push_payloads: list[tuple[str, dict]] = []
    for user_id, distance in active_users:
        notification = build_notification(distance)

        pipe.publish(
            user_channel(user_id),
            notification.model_dump_json(),
        )
        push_payloads.append((user_id, build_push_payload(distance)))

    subscriber_counts = await pipe.execute()

    # 離線但已訂閱推播的使用者：只送系統推播（冪等，失敗的訂閱會被清除）
    for user_id, distance in offline_push_users:
        push_payloads.append((user_id, build_push_payload(distance)))

    push_results = await asyncio.gather(
        *(
            push.send_push_notifications(redis, user_id, payload)
            for user_id, payload in push_payloads
        ),
        return_exceptions=True,
    )
    push_delivered_count = sum(
        result for result in push_results if isinstance(result, int)
    )

    # 4. 統計：subscriber_count > 0 代表該使用者的 WebSocket 在線
    delivered_to = [
        {
            "user_id": user_id,
            "distance_meters": distance,
            "subscriber_count": count,
        }
        for (user_id, distance), count in zip(active_users, subscriber_counts)
        if count > 0
    ]
    failed_count = len(active_users) - len(delivered_to)

    return {
        "event_id": broadcast.event_id,
        "total_nearby_users": len(nearby_users),
        "active_user_count": len(active_users),
        "offline_push_user_count": len(offline_push_users),
        "radius_meters": broadcast.radius_meters,
        "delivered_count": len(delivered_to),
        "failed_count": failed_count,
        "push_delivered_count": push_delivered_count,
        "delivered_to": delivered_to[:20],  # 限制回傳數量避免過大
    }
