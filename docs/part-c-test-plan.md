# Part C 獨立測試計畫

## 1. 測試目標

Part C 的測試目標不是測完整系統，也不是測 Docker / K8s，而是確認這三件事穩定正確：

1. 使用者目前座標可以正確寫入 Redis GEO。
2. 系統可以正確查出指定半徑內的使用者。
3. 線上的附近使用者可以透過 WebSocket 收到通知。

一句話：

> 只要能證明「附近的人收到通知，遠方的人不會收到通知」，Part C 的核心就成立。

## 2. 測試邊界

Part C 要測：

1. Location Service 的位置更新 API。
2. Redis GEO 的附近查詢結果。
3. Notification Service 的 WebSocket 連線。
4. Redis Pub/Sub 到 WebSocket 的通知轉送。
5. Event Service 呼叫後，附近使用者是否收到通知。

Part C 不需要測：

1. 前端地圖 UI。
2. 使用者登入。
3. 事件資料庫 CRUD。
4. Dockerfile、Docker Compose、K8s YAML。
5. HPA、自動擴展、Pod 容錯與壓測。

Docker / K8s 測試屬於 Part D。Part C 只需提供服務需求與測試步驟給 Part D。

## 3. 測試層級

| 層級 | 測什麼 | 是否 Part C 必做 |
|------|--------|------------------|
| 手動 API 測試 | 用 Swagger / Postman 測 `/locations`、`/locations/nearby` | 必做 |
| Redis GEO 行為測試 | 確認半徑內外使用者查詢正確 | 必做 |
| WebSocket 手動測試 | 開 WebSocket client，確認收到通知 | 必做 |
| 跨服務手動測試 | Location -> Event -> Notification -> WebSocket | 必做 |
| 自動化測試 | 用 pytest 測 API 與 WebSocket | 建議 |
| Docker / K8s 測試 | 容器、部署、自動擴展 | Part D 負責 |

## 4. 測試資料

建議固定使用以下三個測試使用者：

| user_id | 位置設定 | 預期 |
|---------|----------|------|
| `alice` | 事件附近，500 公尺內 | 應該收到通知 |
| `bob` | 事件附近，500 公尺內 | 應該收到通知 |
| `carol` | 事件 500 公尺外 | 不應該收到通知 |

範例事件座標：

```text
latitude: 25.0330
longitude: 121.5654
```

範例使用者座標：

```text
alice: latitude 25.0330, longitude 121.5654
bob:   latitude 25.0340, longitude 121.5660
carol: latitude 25.0400, longitude 121.5800
```

## 5. 手動測試案例

### TC-C-001：更新使用者位置

目的：確認 Location Service 可以接收使用者位置並寫入 Redis GEO。

API：

```http
POST /locations
```

Request：

```json
{
  "user_id": "alice",
  "latitude": 25.0330,
  "longitude": 121.5654
}
```

預期結果：

1. API 回傳成功。
2. 回傳內容包含 `user_id`。
3. 後續 nearby 查詢可以找到 `alice`。

### TC-C-002：查詢 500 公尺內使用者

目的：確認 Redis GEO 可以正確查詢附近使用者。

前置條件：

1. 已更新 `alice` 在事件附近。
2. 已更新 `bob` 在事件附近。
3. 已更新 `carol` 在事件 500 公尺外。

API：

```http
GET /locations/nearby?latitude=25.0330&longitude=121.5654&radius_meters=500
```

預期結果：

1. 回傳結果包含 `alice`。
2. 回傳結果包含 `bob`。
3. 回傳結果不包含 `carol`。

### TC-C-003：同一使用者移動後位置會更新

目的：確認同一個 `user_id` 更新位置後，Redis GEO 以最新位置為準。

步驟：

1. 將 `alice` 放在事件附近。
2. 查詢 nearby，確認 `alice` 在結果中。
3. 將 `alice` 移到遠方座標。
4. 再次查詢原事件座標附近。

預期結果：

1. 第一次 nearby 查詢包含 `alice`。
2. 第二次 nearby 查詢不包含 `alice`。

### TC-C-004：WebSocket 可以連線

目的：確認 Notification Service 可以接受 WebSocket 連線。

WebSocket URL：

```text
ws://localhost:8003/ws/alice
```

預期結果：

1. WebSocket 連線成功。
2. 連線保持開啟，不會立刻斷線。

### TC-C-005：通知單一線上使用者

目的：確認 Notification Service 可以把通知推送給指定使用者。

前置條件：

1. 開啟 WebSocket client，連到 `ws://localhost:8003/ws/alice`。

API：

```http
POST /notify/alice
```

Request：

```json
{
  "event_id": "evt_001",
  "title": "圖書館 3 樓有空位",
  "message": "窗邊大約還有 10 個座位。",
  "latitude": 25.0330,
  "longitude": 121.5654,
  "severity": "info",
  "distance_meters": 120.5
}
```

預期結果：

1. API 回傳成功。
2. `alice` 的 WebSocket client 收到通知 JSON。
3. 通知內容包含正確的 `event_id` 與 `title`。

### TC-C-006：附近使用者收到事件通知

目的：確認完整資料流可以從事件發布一路推到 WebSocket。

前置條件：

1. `alice` 已在事件 500 公尺內。
2. `bob` 已在事件 500 公尺內。
3. `carol` 已在事件 500 公尺外。
4. `alice`、`bob`、`carol` 都已開啟 WebSocket client。

API：

```http
POST /events
```

Request：

```json
{
  "title": "圖書館 3 樓有空位",
  "message": "窗邊大約還有 10 個座位。",
  "latitude": 25.0330,
  "longitude": 121.5654,
  "severity": "info",
  "radius_meters": 500
}
```

預期結果：

1. `alice` 收到 WebSocket 通知。
2. `bob` 收到 WebSocket 通知。
3. `carol` 不會收到通知。
4. `/events` 回傳的 `nearby_user_count` 至少為 2。

## 6. 自動化測試建議

如果時間足夠，Part C 可以補上以下 pytest 測試。

### Location Service

| 測試名稱 | 測試內容 | 預期結果 |
|----------|----------|----------|
| `test_update_location_success` | 更新合法座標 | status 200 |
| `test_nearby_users_in_radius` | 查詢 500 公尺內使用者 | 包含半徑內 user |
| `test_nearby_users_outside_radius` | 查詢 500 公尺內使用者 | 不包含半徑外 user |
| `test_user_move_updates_location` | 同一 user 更新位置 | nearby 結果以最新位置為準 |
| `test_invalid_latitude_rejected` | latitude 超出範圍 | status 422 |
| `test_invalid_longitude_rejected` | longitude 超出範圍 | status 422 |

### Notification Service

| 測試名稱 | 測試內容 | 預期結果 |
|----------|----------|----------|
| `test_websocket_connect` | 連線 `/ws/{user_id}` | 連線成功 |
| `test_notify_connected_user` | 對已連線使用者送通知 | WebSocket 收到訊息 |
| `test_notify_unconnected_user` | 對未連線使用者送通知 | API 不失敗 |
| `test_no_cross_user_notification` | 通知 `alice` | `bob` 不應收到 |

### Cross-Service

| 測試名稱 | 測試內容 | 預期結果 |
|----------|----------|----------|
| `test_event_notifies_nearby_users` | 發布事件通知附近使用者 | 半徑內收到 |
| `test_event_does_not_notify_far_user` | 遠方使用者在線 | 遠方使用者不收到 |
| `test_moved_user_notification_changes` | 使用者移動後再發事件 | 通知結果跟著新位置改變 |

## 7. 驗收標準

Part C 可視為第一階段完成，如果以下條件全部通過：

1. 可以成功更新 `alice`、`bob`、`carol` 的位置。
2. nearby 查詢可以正確分辨 500 公尺內外。
3. WebSocket 可以連線並保持開啟。
4. 對單一使用者推播通知時，指定使用者可以收到。
5. 發布事件後，半徑內使用者收到通知，半徑外使用者不收到。
6. C 能提供 Part D 所需的服務需求與測試步驟。

## 8. Demo 前檢查清單

Demo 前，Part C 至少確認：

1. 三個測試使用者座標固定且記錄清楚。
2. WebSocket client 可以同時開三個使用者。
3. nearby 查詢結果符合預期。
4. 發布事件後，通知內容包含 `event_id`、`title`、`message`、`latitude`、`longitude`。
5. 遠方使用者不會收到通知。
6. 如果 WebSocket 沒收到通知，知道要先檢查：使用者是否在線、座標是否在半徑內、Redis 是否有位置資料。

## 9. 常見失敗原因

| 問題 | 可能原因 | 檢查方式 |
|------|----------|----------|
| nearby 查不到人 | 座標經緯度填反 | 檢查 request 中 latitude / longitude |
| nearby 查到太多人 | radius_meters 設太大 | 確認 radius 是否為 500 |
| WebSocket 沒收到通知 | 使用者沒有連線 | 先確認 `/ws/{user_id}` 已連上 |
| WebSocket 沒收到通知 | user_id 不一致 | 檢查位置更新、WS URL、notify API 是否同一個 user_id |
| 遠方使用者收到通知 | 測試座標距離不夠遠 | 換更遠座標，或降低 radius 測試 |
| API 成功但沒有推播 | Notification Service 沒有 subscriber | 檢查 `subscriber_count` |
