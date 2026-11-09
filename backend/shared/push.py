import asyncio
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PUSH_SUBSCRIPTIONS_PREFIX = "realtime_map_notice:user:push_subscriptions"
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = os.getenv("VAPID_SUBJECT", "mailto:admin@example.com")


def subscription_key(user_id: str) -> str:
    return f"{PUSH_SUBSCRIPTIONS_PREFIX}:{user_id}"


async def has_subscriptions(redis, user_id: str) -> bool:
    """使用者是否曾啟用推播（訂閱紀錄存在 Redis）。

    供廣播與清理流程判斷：離線但有訂閱的使用者仍可透過最後已知
    位置收到 Web Push。"""
    return bool(await redis.exists(subscription_key(user_id)))


def push_is_configured() -> bool:
    return bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY and VAPID_SUBJECT)


async def get_subscriptions(redis, user_id: str) -> list[dict[str, Any]]:
    raw = await redis.get(subscription_key(user_id))
    if not raw:
        return []

    try:
        subscriptions = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Invalid push subscriptions for user %s", user_id)
        return []

    return subscriptions if isinstance(subscriptions, list) else []


async def register_subscription(redis, user_id: str, subscription: dict[str, Any]) -> None:
    subscriptions = await get_subscriptions(redis, user_id)
    endpoint = subscription["endpoint"]
    subscriptions = [item for item in subscriptions if item.get("endpoint") != endpoint]
    subscriptions.append(subscription)
    await redis.set(
        subscription_key(user_id),
        json.dumps(subscriptions),
        ex=60 * 60 * 24 * 365,
    )


async def remove_subscription(redis, user_id: str, endpoint: str) -> bool:
    subscriptions = await get_subscriptions(redis, user_id)
    remaining = [item for item in subscriptions if item.get("endpoint") != endpoint]
    if len(remaining) == len(subscriptions):
        return False

    if remaining:
        await redis.set(
            subscription_key(user_id),
            json.dumps(remaining),
            ex=60 * 60 * 24 * 365,
        )
    else:
        await redis.delete(subscription_key(user_id))
    return True


async def send_push_notifications(redis, user_id: str, payload: dict[str, Any]) -> int:
    if not push_is_configured():
        return 0

    subscriptions = await get_subscriptions(redis, user_id)
    delivered_count = 0
    for subscription in subscriptions:
        status = await _send_one(subscription, payload)
        if status == "expired":
            await remove_subscription(redis, user_id, subscription["endpoint"])
        elif status == "delivered":
            delivered_count += 1
    return delivered_count


# Web Push 明文負載上限 4096 bytes（RFC 8291），加密器還需保留約 128 bytes 餘裕
PUSH_PAYLOAD_LIMIT = 3800


def _fit_payload(payload: dict[str, Any]) -> str:
    """序列化推播負載；超過上限時依序剝離大型欄位、截短訊息，確保可發送。

    防護網：即使上游誤將圖片等大型資料塞進負載，也不讓單則推播整封
    被推播伺服器以 413 拒收（曾導致「帶圖事件收不到通知」）。
    """
    data = json.dumps(payload, ensure_ascii=False)
    if len(data) <= PUSH_PAYLOAD_LIMIT:
        return data

    slim = dict(payload)
    for field in ("analysis", "image_url", "image_base64", "location_label"):
        if slim.pop(field, None) is not None:
            data = json.dumps(slim, ensure_ascii=False)
            if len(data) <= PUSH_PAYLOAD_LIMIT:
                return data

    message = slim.get("message") or ""
    while len(data) > PUSH_PAYLOAD_LIMIT and len(message) > 16:
        message = message[: int(len(message) * 0.6)]
        slim["message"] = f"{message}…"
        data = json.dumps(slim, ensure_ascii=False)
    logger.warning("push payload 超過 %d bytes，已自動瘦身至 %d bytes", PUSH_PAYLOAD_LIMIT, len(data))
    return data


async def _send_one(subscription: dict[str, Any], payload: dict[str, Any]) -> str:
    try:
        from pywebpush import webpush

        await asyncio.to_thread(
            webpush,
            subscription_info=subscription,
            data=_fit_payload(payload),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_SUBJECT},
        )
    except ImportError:
        logger.error("pywebpush is not installed; Web Push is disabled")
        return "failed"
    except Exception as error:
        response = getattr(error, "response", None)
        if getattr(response, "status_code", None) in (404, 410):
            return "expired"
        logger.warning("Web Push delivery failed: %s", error)
        return "failed"
    return "delivered"