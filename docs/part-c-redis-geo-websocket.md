# Part C：Redis GEO + WebSocket 架構

## 1. 角色定位

Part C 負責即時位置與附近通知推送。

一句話說明：

> Part C 記錄每位使用者目前的位置，找出指定半徑內的使用者，並把即時事件通知推送給附近且在線上的使用者。

## 2. 負責範圍

Part C 負責：

1. 接收使用者位置更新。
2. 將使用者目前位置存進 Redis GEO。
3. 根據事件座標查詢附近使用者。
4. 維護 WebSocket 連線。
5. 將事件通知推送給附近且在線上的使用者。

Part C 不負責：

1. 使用者註冊或登入。
2. 完整事件 CRUD。
3. 事件長期儲存。
4. 前端地圖 UI。
5. Kubernetes 自動擴展與壓測操作。

## 3. 目前 Repo 對應

目前 repo 將 Part C 拆成兩個後端服務：

```text
backend/location-service
  接收 GPS 座標更新，並將目前位置存入 Redis GEO。

backend/notification-service
  維護 WebSocket 連線，並推送使用者通知。
```

事件服務負責把這兩部分串起來：

```text
backend/event-service
  建立事件，查詢 Redis GEO 中的附近使用者，並呼叫 notification-service。
```

## 4. 資料流程

### 使用者更新位置

```text
Frontend
  -> POST /locations
  -> location-service
  -> Redis GEO
```

Redis key：

```text
realtime_map_notice:user:locations
```

Redis 操作：

```text
GEOADD realtime_map_notice:user:locations <longitude> <latitude> <user_id>
```

### 前端開啟 WebSocket

```text
Frontend
  -> WS /ws/{user_id}
  -> notification-service
```

notification-service 會訂閱該使用者專屬的 Redis Pub/Sub channel：

```text
realtime_map_notice:user:{user_id}:notifications
```

### 使用者建立事件

```text
Frontend
  -> POST /events
  -> event-service
  -> Redis GEO search
  -> notification-service
  -> WebSocket client
```

Redis 操作：

```text
GEOSEARCH realtime_map_notice:user:locations
  FROMLONLAT <longitude> <latitude>
  BYRADIUS <radius_meters> m
```

## 5. Part C 負責的 API

### Location Service

健康檢查：

```http
GET /healthz
```

更新使用者位置：

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

查詢附近使用者：

```http
GET /locations/nearby?latitude=25.0330&longitude=121.5654&radius_meters=500
```

Response：

```json
{
  "users": ["alice", "bob"]
}
```

### Notification Service

健康檢查：

```http
GET /healthz
```

開啟即時連線：

```http
WS /ws/{user_id}
```

通知單一使用者：

```http
POST /notify/{user_id}
```

Request：

```json
{
  "event_id": "evt_001",
  "title": "Library 3F has seats",
  "message": "About 10 seats near the windows.",
  "latitude": 25.0330,
  "longitude": 121.5654,
  "severity": "info",
  "distance_meters": 120.5
}
```

## 6. 第一個里程碑

Part C 的第一個里程碑要證明三件事：

1. 使用者位置可以更新到 Redis GEO。
2. 系統可以查詢 500 公尺內的附近使用者。
3. 附近且在線上的使用者可以收到 WebSocket 通知。

## 7. 本機 Demo 步驟

啟動服務：

```powershell
docker compose up --build
```

開啟 API 文件：

```text
http://localhost:8001/docs  location-service
http://localhost:8002/docs  event-service
http://localhost:8003/docs  notification-service
```

建議手動測試流程：

1. 開啟 WebSocket client，連到 `ws://localhost:8003/ws/alice`。
2. 呼叫 `POST http://localhost:8001/locations`，將 `alice` 放在事件座標附近。
3. 呼叫 `POST http://localhost:8001/locations`，將 `bob` 放在較遠的位置。
4. 呼叫 `POST http://localhost:8002/events` 建立事件。
5. 確認只有附近且已連線的使用者收到通知。

## 8. 接下來建議實作

Part C 建議接下來依序完成：

1. 加一個簡單的 WebSocket 測試 client，方便本機 Demo。
2. 加入 heartbeat 或 ping/pong 機制，清掉失效連線。
3. 讓 nearby-user 查詢回傳距離，方便除錯。
4. 針對校園座標附近的假使用者，補上 Redis GEO 查詢測試。
5. 記錄團隊 Demo 會使用的固定座標。

## 9. 重要注意事項

Redis GEO 應該只儲存「目前位置查詢」資料，不要存完整使用者個人資料，也不要存永久事件歷史。

notification-service 應該專注在「線上即時推送」。如果使用者離線，MVP 階段可以先略過通知，不需要先做未讀通知儲存。

最後做 K8s Demo 前，Part C 應該先用 Docker Compose 在本機測通。Kubernetes 應該視為部署層，而不是第一個拿來除錯應用邏輯的地方。
