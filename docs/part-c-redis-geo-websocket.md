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
5. Dockerfile、Docker Compose 與 Kubernetes 部署設定。
6. Kubernetes 自動擴展、Pod 容錯與壓測操作。

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

## 4. 跨角色溝通關係

Part C 最主要的合作對象是 Part B 與 Part D，另外也需要和 Part A 對齊前端接收格式。

### Part C 與 Part B：事件與通知流程

Part B 負責事件 API 與商業邏輯，Part C 負責附近使用者查詢與即時推播。

需要對齊：

1. 發布事件後，Part B 要呼叫哪個通知流程。
2. 事件資料格式，例如 `event_id`、`title`、`message`、`latitude`、`longitude`、`severity`。
3. `user_id` 格式必須一致。
4. 預設通知半徑是否為 500 公尺。
5. 附近沒有人時要回傳什麼。
6. 使用者離線時如何處理。MVP 階段建議不儲存未讀通知，只回報沒有線上接收者。

簡單分工：

```text
Part B 決定「發生什麼事件」
Part C 決定「通知誰、怎麼即時送出去」
```

### Part C 與 Part D：服務運行與部署需求

Part D 負責 Docker、K8s、壓測與 Demo 部署。Part C 不負責撰寫或維護 Docker / K8s，但需要告訴 Part D 服務如何運行與如何驗證。

Part C 需要提供給 Part D：

1. 需要 Redis。
2. 服務名稱：`location-service`、`notification-service`。
3. 服務 port：目前本機對外為 `8001` 與 `8003`。
4. 環境變數，例如 `REDIS_URL`。
5. 健康檢查 endpoint：`GET /healthz`。
6. 功能測試方式：更新位置、查附近使用者、開 WebSocket、送通知。
7. WebSocket 多副本時需要注意 Redis Pub/Sub 路由，不能只靠單機記憶體狀態。

簡單分工：

```text
Part C 說明「服務需要什麼、怎麼測」
Part D 負責「怎麼容器化、怎麼部署、怎麼展示擴展與容錯」
```

### Part C 與 Part A：前端 WebSocket 與通知格式

Part A 負責 Web App UI 與地圖畫面。Part C 需要和 Part A 對齊前端怎麼送位置，以及收到通知後要顯示什麼。

需要對齊：

1. 前端多久上傳一次目前位置。
2. 前端連線的 WebSocket URL，例如 `ws://localhost:8003/ws/{user_id}`。
3. 通知 JSON 格式。
4. 前端要顯示哪些欄位，例如標題、訊息、距離、嚴重程度。
5. WebSocket 斷線時，前端是否要自動重連。

簡單分工：

```text
Part A 負責「畫面怎麼呈現」
Part C 負責「通知資料怎麼即時送到」
```

### 溝通優先順序

```text
第一優先：Part C <-> Part B
  對齊事件資料格式、通知半徑、user_id、離線處理。

第二優先：Part C <-> Part D
  對齊 Redis、port、env、health check、測試方式與部署需求。

第三優先：Part C <-> Part A
  對齊位置更新頻率、WebSocket URL、通知 JSON 與前端顯示欄位。
```

## 5. 溝通方式與交付物

Part C 和其他成員溝通時，不建議只用口頭說明。每次對齊後，最好留下簡短文件、API 範例或測試截圖，避免大家理解不同。

### 與 Part B 的溝通方式

Part C 和 Part B 應該用「API contract」溝通。

每次討論後要確認：

1. Part B 發布事件時，送給 C 或相關服務的 request 格式。
2. Part C 回傳給 B 的 response 格式。
3. 錯誤情境怎麼處理，例如附近沒有人、Redis 暫時不可用、Notification Service 無法送出。
4. 欄位名稱要固定，特別是 `user_id`、`latitude`、`longitude`、`radius_meters`。
5. 成功與失敗範例都要有。

建議交付物：

```text
docs/part-c-redis-geo-websocket.md
  API 欄位與資料流程

docs/part-c-test-plan.md
  Part C 驗收案例

Swagger / FastAPI docs
  實際 API request / response
```

建議確認句：

```text
B 發布事件時會送 latitude、longitude、radius_meters。
C 會根據 Redis GEO 找附近 user_id，並透過 notification-service 推播。
附近沒有人時，回傳 nearby_user_count = 0，不視為錯誤。
```

### 與 Part D 的溝通方式

Part C 和 Part D 應該用「服務需求清單」溝通。

每次討論後要確認：

1. Part C 需要哪些服務被啟動。
2. 每個服務使用哪個 port。
3. 需要哪些環境變數。
4. 健康檢查 endpoint 是什麼。
5. Part D 部署完後，Part C 要用哪幾個步驟驗證功能。
6. 如果 K8s 多副本部署 WebSocket，是否仍能透過 Redis Pub/Sub 正確推送通知。

建議交付物：

```text
服務需求清單：
- Redis
- location-service
- notification-service
- event-service

環境變數：
- REDIS_URL

健康檢查：
- GET /healthz

驗證方式：
- POST /locations
- GET /locations/nearby
- WS /ws/{user_id}
- POST /events
```

建議確認句：

```text
D 只要服務可以連到同一個 Redis，C 的 Redis GEO 與 Redis Pub/Sub 才能正常運作。
C 不負責 K8s YAML，但會提供測試步驟給 D 驗證部署是否成功。
```

### 與 Part A 的溝通方式

Part C 和 Part A 應該用「前端接收格式」溝通。

每次討論後要確認：

1. 前端呼叫位置更新 API 的頻率。
2. 前端使用哪個 `user_id` 連 WebSocket。
3. WebSocket 收到通知後，前端要顯示哪些欄位。
4. WebSocket 斷線時，前端是否重連。
5. 前端是否需要顯示距離 `distance_meters`。

建議交付物：

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

建議確認句：

```text
A 只要連到 ws://localhost:8003/ws/{user_id}，收到 nearby event JSON 後顯示通知卡片。
C 會保證通知格式固定；A 不需要知道 Redis GEO 怎麼查。
```

### 建議溝通節奏

```text
每週一次全組同步：
  確認 A/B/C/D 目前 API、port、欄位名稱有沒有變。

C 與 B 每次改 API 前：
  先更新 request / response 範例，再改程式。

C 與 D 每次部署前：
  先確認 env、port、health check、測試步驟。

C 與 A 每次改通知格式前：
  先確認前端 UI 需要哪些欄位。
```

### 溝通原則

1. 口頭討論後，要把結論寫進文件或 issue。
2. API 欄位名稱不要臨時改，改了要通知 A/B/D。
3. `user_id` 是跨服務關鍵欄位，所有人必須用同一套格式。
4. 經緯度欄位要固定使用 `latitude` 與 `longitude`，避免順序填反。
5. C 的 Demo 驗收應以 `docs/part-c-test-plan.md` 為準。

## 6. 資料流程

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

## 7. Part C 負責的 API

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

## 8. 第一個里程碑

Part C 的第一個里程碑要證明三件事：

1. 使用者位置可以更新到 Redis GEO。
2. 系統可以查詢 500 公尺內的附近使用者。
3. 附近且在線上的使用者可以收到 WebSocket 通知。

## 9. 本機功能測試步驟

Part C 的重點是確認 Redis GEO 與 WebSocket 功能正確。Docker Compose 與 K8s 的撰寫、維護、部署展示由 Part D 負責。

如果 Part D 已經準備好本機開發環境，可以用下列方式啟動服務：

```powershell
docker compose up --build
```

開啟 API 文件：

```text
http://localhost:8001/docs  location-service
http://localhost:8002/docs  event-service
http://localhost:8003/docs  notification-service
```

Part C 建議手動測試流程：

1. 開啟 WebSocket client，連到 `ws://localhost:8003/ws/alice`。
2. 呼叫 `POST http://localhost:8001/locations`，將 `alice` 放在事件座標附近。
3. 呼叫 `POST http://localhost:8001/locations`，將 `bob` 放在較遠的位置。
4. 呼叫 `POST http://localhost:8002/events` 建立事件。
5. 確認只有附近且已連線的使用者收到通知。

## 10. 接下來建議實作

Part C 建議接下來依序完成：

1. 加一個簡單的 WebSocket 測試 client，方便本機 Demo。
2. 加入 heartbeat 或 ping/pong 機制，清掉失效連線。
3. 讓 nearby-user 查詢回傳距離，方便除錯。
4. 針對校園座標附近的假使用者，補上 Redis GEO 查詢測試。
5. 記錄團隊 Demo 會使用的固定座標。
6. 提供給 Part D 需要的服務啟動需求、環境變數與測試方式。

## 11. 重要注意事項

Redis GEO 應該只儲存「目前位置查詢」資料，不要存完整使用者個人資料，也不要存永久事件歷史。

notification-service 應該專注在「線上即時推送」。如果使用者離線，MVP 階段可以先略過通知，不需要先做未讀通知儲存。

Part C 只需要確認 Redis GEO 與 WebSocket 功能在本機可測。Docker Compose 與 K8s 部署細節由 Part D 負責，Part C 可配合提供服務啟動需求、環境變數與測試方式。
