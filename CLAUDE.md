# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

即時校園地圖通知系統 — 使用者在地圖上回報事件（交通事故、施工、人群聚集、設備故障、道路封閉等），系統只通知事件座標半徑內（預設 1km）的使用者。React + Leaflet 前端、三個 FastAPI 微服務 + Redis 後端、nginx 反向代理。

**線上展示**: https://map2.avision-gb10.org

## Commands

### Backend
```bash
# 啟動所有服務（Redis + 3 FastAPI 微服務 + nginx）
docker compose up --build -d

# 停止所有服務
docker compose down

# 查看日誌
docker compose logs -f event-service
```

### Frontend
```bash
cd web-app
npm run dev       # Vite dev server on :5173
npm run build     # TypeScript check + production build
npm run lint      # ESLint
```

### 壓力測試
```bash
# 1000 人壓測（需服務運行中）
python stress_test.py
```

## Architecture

三個 FastAPI 微服務 + Redis 7 + nginx + React 前端：

```
Browser → nginx (:8080→:8095) ─→ Location Service (:8001, 4 workers) → Redis GEO
                               → Event Service (:8002, 4 workers)    → Redis GEO + LIST + PUBLISH
                               ← Notification Service (:8003, 1 worker) ← Redis SUBSCRIBE + WebSocket
Browser ← nginx (/ws/*) ←─────────────────────────────────────────────┘
```

- **Location Service** (`backend/location-service/`) — 接收 GPS 座標，存入 Redis GEO，查詢附近使用者
- **Event Service** (`backend/event-service/`) — 建立事件（冪等 client_event_id + TTL）、持久化到 Redis LIST、透過 Redis Pub/Sub 發布通知（不再 HTTP fanout）、支援事件過期（expires_in 分鐘）、留言功能
- **Notification Service** (`backend/notification-service/`) — 管理使用者 WebSocket 連線、訂閱 Redis Pub/Sub channel、本地 geosearch + WS 推播、離線通知佇列、app-level ping/pong 心跳
- **nginx** (`nginx/nginx.conf`) — 反向代理：靜態前端、`/api/*` 路由到後端服務、`/ws/*` 到 notification service（WebSocket upgrade）

### Shared Code (`backend/shared/`)
- `schemas.py` — Pydantic models: `LocationUpdate`, `EventCreate`（含 expires_in 1-1440 分鐘）, `EventNotification`, `EventRecord`, `Comment`
- `config.py` — 環境變數設定（REDIS_URL, CORS, 冪等 TTL, event history max, structured logging）
- `redis_client.py` — 共用 Redis connection pool（max_connections=20, socket_timeout=5）
- `cors.py` — CORS middleware 設定

### Frontend (`web-app/src/`)
- `components/` — MapView (Leaflet 地圖), EventForm（常用事件快選 4×2 格 + 有效期限下拉）, NotificationBanner（緊急/一般通知）, EventDetailPanel（事件詳情 + 留言）
- `hooks/` — useGeolocation (瀏覽器 Geolocation API), useNotificationSocket (WebSocket 自動 wss:// 偵測)
- `services/` — API clients（location, event, websocket）
- `types.ts` / `api.ts` — TypeScript 型別定義 + API 呼叫封裝

## Key Design Decisions

- **Ports**: 服務內部 :8000，Docker 映射 :8001/:8002/:8003；nginx :8080 映射到 host :8095
- **Redis GEO** 做空間查詢（非 PostGIS）— 保持技術棧簡單
- **Redis Pub/Sub** 做事件推播 — event-service 只 `PUBLISH` 一條命令（微秒級），notification-service 訂閱 channel 後本地 geosearch + WS 推播。取代原本的 HTTP fanout，消除跨服務呼叫瓶頸
- **Gunicorn + Uvicorn workers**: location-service 4 workers, event-service 4 workers（多核利用）, notification-service 1 worker（WebSocket 需要 sticky connection）
- **冪等性**: Event Service 用 `client_event_id`（前端 `crypto.randomUUID()`）+ Redis TTL 防重複處理
- **事件持久化**: Redis LIST（最新 100 筆），`GET /events` 查詢，自動過濾過期事件
- **事件過期**: `expires_in` 欄位（1-1440 分鐘，預設 30），後端計算 `expires_at` timestamp
- **留言系統**: Redis LIST 存儲（每事件最多 100 則），`POST/GET /events/{id}/comments`
- **離線佇列**: 使用者離線時通知存入 Redis LIST `pending:{user_id}`，WebSocket 重連後回放
- **Redis Connection Pool**: FastAPI lifespan 管理，graceful shutdown
- **Structured Logging**: `logging` 模組，格式一致，`LOG_LEVEL` 環境變數控制
- **Docker Security**: 所有容器以非 root 帳號（`appuser`）執行
- **嚴重程度**: `info`（一般）和 `urgent`（緊急，觸發距離推播）
- **通知範圍**: 每事件可設定（UI slider 100–2000m），預設 500m
- **CORS**: `CORS_ALLOW_ORIGINS` 環境變數，含 `map2.avision-gb10.org`
- **WebSocket URL**: 自動偵測頁面協定（`ws:`/`wss:`）+ host，無需硬編碼
- **UI 語言**: 繁體中文

## 壓力測試結果

### Docker Compose 部署（固定 Pod）

| 規模 | Location | Event | Comment | Query | 總 RPS |
|------|----------|-------|---------|-------|--------|
| 200 人 | 99.1% ✅ | 99.0% ✅ | 100% ✅ | 100% ✅ | 112 |
| 500 人 | 98.4% ✅ | 100% ✅ | 99.1% ✅ | 100% ✅ | 277 |
| 1000 人 | 95.5% ⚠️ | 100% ✅ | 100% ✅ | 100% ✅ | 271 |

Redis Pub/Sub 架構下，Event/Comment/Query 在 1000 人時仍 100% 成功率。

### Kubernetes HPA 壓力測試（自動擴縮 vs 固定 Pod）

漸進式壓測（300→3000→300 用戶），HPA 配置：maxReplicas 8、targetCPU 30%、cpu request 100m：

| 並發用戶 | 無 HPA Location | 無 HPA Event | 有 HPA Location | 有 HPA Event | Pods（有HPA） |
|----------|-----------------|--------------|-----------------|--------------|---------------|
| 300 | 100% | 100% | 100% | 100% | 4 / 1 |
| 800 | 99.5% | 99.9% | **100%** | **100%** | 8 / 2 |
| 1500 | 93.2% | 95.5% | **99.1%** | **98.5%** | 8 / 2 |
| 2000 | 83.9% | 78.5% | **98.1%** | **99.9%** | 8 / 3 |
| 3000 | 94.8% | **0%** ❌ | **100%** | **100%** | 8 / 3 |

有 HPA 在 3000 人並發下仍維持 100% 成功率；無 HPA 在 3000 人時 Event Service 完全崩潰。
完整圖表比較：`hpa_comparison.html`。Location Service 是下一個瓶頸（可加 workers 或 Redis pipeline batch write）。

## Deployment

Docker Compose + nginx + Cloudflare Tunnel：
- `docker compose up --build -d` 啟動所有服務
- nginx 提供前端靜態檔 + API/WebSocket 反向代理
- Cloudflare Tunnel: `map2.avision-gb10.org` → `localhost:8095`
- 記憶體佔用 ~470MB（含 gunicorn 4 workers）

## Language

文件和程式碼註解使用繁體中文。台灣大學專題作品。
