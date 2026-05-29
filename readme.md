# realtime_map_notice

`realtime_map_notice` 是一個專屬校園或特定街區使用的「即時動態地圖 Web App」專題。使用者可以在地圖上插旗回報突發狀況，例如交通事故、施工、人群聚集、設備故障或緊急事件。

專案核心亮點是：當有人發布緊急事件時，系統只通知目前位於該座標半徑內的使用者，減少傳統論壇或群組常見的資訊延遲與無關通知。

**線上展示**: https://map2.avision-gb10.org

## 專題目標

- 建立一個能展示即時地圖、即時定位與區域推播的 Web App 架構。
- 使用微服務拆分位置更新、事件發布與通知推播。
- 使用 Redis GEO 暫存即時座標，支援快速查詢附近使用者。
- 使用 WebSocket 讓伺服器主動推播事件到使用者端。
- 使用 Docker Compose 部署，Cloudflare Tunnel 對外。
- 壓力測試驗證 1000 人同時上線穩定性。

## 使用情境

**一般事件（快選按鈕 4×2 格）：**
- 🚗 交通事故
- 🚧 施工中
- 👥 人群聚集
- 🔧 設備故障
- 🚫 道路封閉
- ⚠️ 危險物品
- 📢 噪音騷擾
- ✏️ 其他自訂

**緊急事件：**
- 路上有走失的狗狗
- 某區域施工或封路
- 天橋或走道臨時無法通行
- 校內突發安全提醒

緊急事件會依照事件座標查詢半徑範圍內的使用者，再透過 WebSocket 推播。事件可設定有效期限（15 分鐘 ~ 24 小時），過期自動消失。

## 專案結構

```text
realtime_map_notice/
├── backend/
│   ├── location-service/        # 接收 GPS 座標更新（gunicorn 4 workers）
│   ├── event-service/           # 發布事件、Redis Pub/Sub 推播、留言（gunicorn 4 workers）
│   ├── notification-service/    # WebSocket 即時推播、離線佇列（1 worker）
│   └── shared/                  # 共用 schema、設定與 Redis client
├── web-app/                     # React + Vite + Leaflet + TypeScript 前端
├── nginx/                       # nginx 反向代理設定
├── stress_test.py               # 異步壓力測試（200/500/1000 人）
├── docker-compose.yml           # Docker Compose 部署
├── Dockerfile.web               # 前端多階段構建
├── entrypoint.sh                # gunicorn 入口腳本
├── readme.md                    # 專案總覽
├── CLAUDE.md                    # 開發指引
├── development.md               # 開發與 Demo 流程
└── system.md                    # 系統架構設計
```

## 技術選型

- **前端**: React + Vite + TypeScript, Leaflet 地圖, browser Geolocation API
- **後端**: Python FastAPI (三個微服務)
- **即時通訊**: WebSocket（app-level ping/pong 心跳）
- **位置儲存**: Redis GEO
- **事件推播**: Redis Pub/Sub（取代 HTTP fanout，1000 人壓測 Event 100% 成功）
- **事件持久化**: Redis LIST（最新 100 筆，自動過濾過期事件）
- **留言系統**: Redis LIST（每事件最多 100 則）
- **離線佇列**: Redis LIST `pending:{user_id}`，重連後回放
- **容器**: Docker Compose + gunicorn + uvicorn workers
- **反向代理**: nginx（前端靜態 + API 路由 + WebSocket upgrade）
- **對外**: Cloudflare Tunnel (`map2.avision-gb10.org`)
- **安全性**: 非 root 容器（`appuser`）、CORS 設定、冪等性（client_event_id + TTL）
- **壓測**: Python asyncio + httpx

## 核心 API

| 服務 | Endpoint | 用途 |
|------|----------|------|
| Location | `POST /locations` | 接收 GPS 座標 → Redis GEO |
| Location | `GET /locations/nearby` | 查詢附近使用者 |
| Event | `POST /events` | 建立事件 → Redis Pub/Sub 推播 |
| Event | `GET /events` | 查詢歷史事件（自動過濾過期） |
| Event | `POST /events/{id}/comments` | 新增留言 |
| Event | `GET /events/{id}/comments` | 查詢留言 |
| Notification | `WS /ws/{user_id}` | WebSocket 即時通知連線 |

## 壓力測試結果

### Docker Compose 部署（固定 Pod）

| 規模 | Location | Event | Comment | Query | 總 RPS |
|------|----------|-------|---------|-------|--------|
| 200 人 | 99.1% | 99.0% | 100% | 100% | 112 |
| 500 人 | 98.4% | **100%** | 99.1% | **100%** | 277 |
| 1000 人 | 95.5% | **100%** | **100%** | **100%** | 271 |

Redis Pub/Sub 解耦後，Event/Comment/Query 在 1000 人時仍零失敗。

### Kubernetes HPA 壓力測試（自動擴縮 vs 固定 Pod）

使用漸進式壓測腳本（300→3000→300 用戶），比較無 HPA（固定 1 Pod）與有 HPA（自動擴展至 8 Pods）的差異：

| 並發用戶 | 無 HPA Location | 無 HPA Event | 有 HPA Location | 有 HPA Event | Pods（有HPA） |
|----------|-----------------|--------------|-----------------|--------------|---------------|
| 300 | 100% | 100% | 100% | 100% | 4 / 1 |
| 800 | 99.5% | 99.9% | **100%** | **100%** | 8 / 2 |
| 1500 | 93.2% | 95.5% | **99.1%** | **98.5%** | 8 / 2 |
| 2000 | 83.9% | 78.5% | **98.1%** | **99.9%** | 8 / 3 |
| 3000 | 94.8% | **0%** ❌ | **100%** | **100%** | 8 / 3 |

**關鍵發現**：有 HPA 在 3000 人並發下仍維持 100% 成功率，無 HPA 在 3000 人時 Event Service 完全崩潰。HPA 配置：maxReplicas 8、targetCPU 30%、cpu request 100m。

完整圖表比較報告：[hpa_comparison.html](./hpa_comparison.html)

## 四人分工

- 成員 A：Web App、地圖介面、瀏覽器定位、UI/UX。
- 成員 B：後端 API、事件發布、商業邏輯。
- 成員 C：Redis GEO、WebSocket、即時推播。
- 成員 D：Docker、部署、壓測與 Demo。

## 相關文件

- [CLAUDE.md](./CLAUDE.md)：開發指引（架構、設計決策、壓測數據）。
- [development.md](./development.md)：開發環境、執行方式、Demo 流程。
- [system.md](./system.md)：系統架構、API、容量規劃。
