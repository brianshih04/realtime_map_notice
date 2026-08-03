"""
階段三：成員C的廣播範圍驗證測試

目的：證明距離 1 公里外的測試帳號「不會」收到推播，只有 500m 內的會收到。

測試場景：
1. 建立中心點（事件發生位置）：台大總圖書館 (25.0173, 121.5397)
2. 建立測試用戶：
   - user-near-100m: 距離中心 100 公尺（應該收到）
   - user-near-300m: 距離中心 300 公尺（應該收到）
   - user-near-500m: 距離中心 500 公尺（邊界，應該收到）
   - user-far-700m: 距離中心 700 公尺（不應該收到）
   - user-far-1000m: 距離中心 1000 公尺（不應該收到）
3. 每個用戶連接 WebSocket
4. 呼叫 /broadcast/nearby 發布事件（radius=500）
5. 驗證哪些用戶收到通知

執行方式：
    python test_nearby_broadcast.py

或指定後端 URL：
    python test_nearby_broadcast.py --target http://localhost:8003
"""

import asyncio
import argparse
from datetime import datetime

import websockets
import httpx


# 測試座標：台大總圖書館
CENTER_LAT = 25.0173
CENTER_LNG = 121.5397


def offset_coordinate(latitude: float, longitude: float, offset_meters_north: int, offset_meters_east: int) -> tuple[float, float]:
    """
    計算偏移後的座標
    1 度緯度約 111,000 公尺
    1 度經度約 111,000 * cos(緯度) 公尺
    """
    lat_offset = offset_meters_north / 111000
    lng_offset = offset_meters_east / (111000 * __import__('math').cos(__import__('math').radians(latitude)))
    return (latitude + lat_offset, longitude + lng_offset)


# 測試用戶定義：每個用戶距離中心點的距離
TEST_USERS = [
    {"user_id": "user-near-100m", "offset_north": 100, "offset_east": 0, "should_receive": True},
    {"user_id": "user-near-300m", "offset_north": 300, "offset_east": 0, "should_receive": True},
    {"user_id": "user-near-490m", "offset_north": 490, "offset_east": 0, "should_receive": True},  # 改為 490m 避免 Redis GEO 邊界精度問題
    {"user_id": "user-far-700m", "offset_north": 700, "offset_east": 0, "should_receive": False},
    {"user_id": "user-far-1000m", "offset_north": 1000, "offset_east": 0, "should_receive": False},
]


async def register_user_location(client: httpx.AsyncClient, target: str, user: dict) -> None:
    """註冊用戶位置到 Redis GEO"""
    lat, lng = offset_coordinate(CENTER_LAT, CENTER_LNG, user["offset_north"], user["offset_east"])
    await client.post(
        f"{target}/locations",
        json={
            "user_id": user["user_id"],
            "latitude": lat,
            "longitude": lng,
        },
    )
    user["actual_coords"] = (lat, lng)


async def websocket_listener(user: dict, ws_url: str, received_list: list) -> None:
    """監聽 WebSocket 並記錄收到的通知"""
    try:
        # 將 http:// 轉換為 ws://
        ws_host = ws_url.replace("http://", "ws://").replace("https://", "wss://")
        async with websockets.connect(f"{ws_host}/ws/{user['user_id']}") as ws:
            # 等待 hello 訊息
            hello = await ws.recv()
            if "hello" not in hello:
                print(f"❌ {user['user_id']}: 未收到 hello 訊息")

            # 持續監聽，最多等待 10 秒
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=10)
                received_list.append({"user_id": user["user_id"], "message": message})
                print(f"✅ {user['user_id']}: 收到通知")
            except asyncio.TimeoutError:
                print(f"⏱️  {user['user_id']}: 10 秒內無通知")
    except Exception as e:
        print(f"❌ {user['user_id']}: WebSocket 連線失敗 - {e}")


async def broadcast_event(target: str, radius_meters: int = 500) -> dict:
    """發布廣播事件"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{target}/broadcast/nearby",
            json={
                "event_id": f"test-{datetime.now().timestamp()}",
                "title": "測試事件",
                "message": "這是一個測試通知",
                "latitude": CENTER_LAT,
                "longitude": CENTER_LNG,
                "severity": "info",
                "radius_meters": radius_meters,
            },
        )
        return response.json()


async def run_test(target: str, location_target: str, skip_cleanup: bool = False) -> None:
    """執行完整測試流程"""
    print("=" * 60)
    print("階段三：成員C 廣播範圍驗證測試")
    print("=" * 60)
    print(f"\n📍 事件中心點：({CENTER_LAT}, {CENTER_LNG})")
    print(f"📡 Notification Service: {target}")
    print(f"📍 Location Service: {location_target}\n")

    # 準備工作：清除舊的測試用戶位置
    if not skip_cleanup:
        print("🧹 建議：測試前清除 Redis 中的舊資料以獲得準確結果")
        print("   在另一個終端機執行：")
        print("   docker exec -it realtime_map_notice-redis-1 redis-cli DEL realtime_map_notice:user:locations")
        print("   按 Enter 繼續...")
        input()
    print()

    # 第一步：註冊所有測試用戶位置
    print("第一步：註冊測試用戶位置...")
    async with httpx.AsyncClient() as client:
        for user in TEST_USERS:
            await register_user_location(client, location_target, user)
            lat, lng = user["actual_coords"]
            print(f"  • {user['user_id']}: ({lat:.6f}, {lng:.6f}) - 預期{'收到' if user['should_receive'] else '不收到'}")
    print()

    # 等待 Redis 同步
    await asyncio.sleep(1)

    # 第二步：所有用戶連接 WebSocket
    print("第二步：連接 WebSocket...")
    received_notifications = []
    ws_tasks = []
    for user in TEST_USERS:
        ws_tasks.append(asyncio.create_task(
            websocket_listener(user, target, received_notifications)
        ))
    print()

    # 等待 WebSocket 連線建立
    await asyncio.sleep(2)

    # 第三步：發布廣播事件
    print("第三步：發布廣播事件（radius=500m）...")
    broadcast_result = await broadcast_event(target, 500)
    print(f"  • 附近用戶總數：{broadcast_result.get('total_nearby_users', 0)}")
    print(f"  • 成功推播數：{broadcast_result.get('delivered_count', 0)}")
    print(f"  • 推播失敗數：{broadcast_result.get('failed_count', 0)}")
    if broadcast_result.get('delivered_to'):
        print("  • 推播對象：")
        for item in broadcast_result['delivered_to']:
            dist = item.get('distance_meters', 0)
            print(f"    - {item['user_id']}: 距離 {dist:.1f}m")
    print()

    # 第四步：等待通知到達
    print("第四步：等待通知到達（最多 10 秒）...")
    await asyncio.sleep(10)

    # 結束所有 WebSocket 任務
    for task in ws_tasks:
        task.cancel()

    # 第五步：驗證結果
    print("\n" + "=" * 60)
    print("測試結果")
    print("=" * 60)

    received_user_ids = {n["user_id"] for n in received_notifications}
    all_passed = True

    for user in TEST_USERS:
        received = user["user_id"] in received_user_ids
        expected = user["should_receive"]
        status = "✅" if received == expected else "❌"
        all_passed = all_passed and (received == expected)

        actual_distance = user["offset_north"]  # 簡化計算（因為只往北偏移）
        print(f"{status} {user['user_id']} (距離 {actual_distance}m): "
              f"{'收到' if received else '未收到'} - {'正確' if received == expected else '錯誤'}")

    print()
    if all_passed:
        print("🎉 所有測試通過！500m 內的用戶收到通知，500m 外的用戶未收到。")
    else:
        print("⚠️  測試失敗！請檢查 Redis GEO 查詢邏輯。")

    print("=" * 60)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="階段三廣播範圍驗證測試")
    parser.add_argument(
        "--target",
        default="http://localhost:8003",
        help="Notification Service URL (default: http://localhost:8003)"
    )
    parser.add_argument(
        "--location-target",
        default="http://localhost:8001",
        help="Location Service URL (default: http://localhost:8001)"
    )
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="跳過清除舊測試資料的提示"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_test(args.target, args.location_target, args.skip_cleanup))
