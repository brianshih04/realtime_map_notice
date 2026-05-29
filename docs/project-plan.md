# 專案詳細計畫

這份文件把 `realtime_map_notice` 拆成可執行的開發階段、四人分工、Demo 流程與驗收標準。目標不是一次做成正式產品，而是在專題期限內完成一個技術重點清楚、展示效果強、分工明確的系統。

## 專案範圍

必做功能：

- Web App 顯示校園或街區地圖。
- 使用者可以在地圖上發布事件。
- 使用者位置會定期上傳到 Location Service。
- Web App 地圖上的使用者位置與事件 marker 需要隨資料更新。
- 後端使用 Redis GEO 儲存即時位置。
- 發布緊急事件時，只通知半徑 500 公尺內使用者。
- 使用 WebSocket 將事件主動推送到前端。
- 使用 Python 腳本模擬初期 500-1,000 位虛擬使用者持續移動，進階展示可提高到 3,000 位。
- 使用 Kubernetes 展示 Location Service 自動擴展。
- 使用 Kubernetes 展示 Notification Service Pod 容錯。

暫不納入第一版：

- 正式會員註冊與密碼管理。
- 複雜社群功能，例如留言、按讚、好友。
- 長期軌跡分析與歷史熱區報表。
- 原生手機 App。
- 正式上架與公開營運。

## 階段規劃

### 第 1 階段：架構與後端骨架

目標：

- 先讓系統的微服務邊界清楚。
- 建立可本機啟動的後端環境。
- 讓每個組員有明確可接手的模組。

工作項目：

- 建立 `location-service`，提供位置上傳 API。
- 建立 `event-service`，提供事件發布 API。
- 建立 `notification-service`，提供 WebSocket 連線與通知 API。
- 建立 `shared`，放共用 schema、Redis client 與設定。
- 建立 Redis GEO key 命名規則。
- 依照 [../system.md](../system.md) 定義位置更新欄位、last_seen TTL 與地圖更新驗收標準。
- **確認每個服務的 fastapi.middleware.cors.CORSMiddleware 正確允許前端 origin。**
- **建立根目錄 .dockerignore，避免 .git 與 __pycache__ 進入 Docker build context。**
- 建立 `docker-compose.yml`，讓本機可以一次啟動所有後端服務。
- 建立每個服務的 Dockerfile。

交付物：

- 三個 FastAPI 微服務。
- Redis 連線設定。
- 基本 API 文件，可透過 `/docs` 查看。
- 本機啟動文件。

驗收標準：

- 可以成功呼叫 `POST /locations` 更新使用者座標。
- 可以成功呼叫 `GET /locations/nearby` 查詢附近使用者。
- 可以成功呼叫 `POST /events` 建立事件。
- Notification Service 可以接受 WebSocket 連線。

### 第 2 階段：Web App 前端

目標：

- 建立可展示的使用者介面。
- 讓教授能直觀看到「地圖、插旗、附近通知」。
- 前端以瀏覽器為主，不開發原生手機 App。

工作項目：

- 建立 Web App 專案，**先決定地圖函式庫（Leaflet / MapLibre GL JS / Google Maps），評估瀏覽器定位相容性與開發難度。**
- 設計全螢幕地圖主畫面。
- 依照 [../web-app/README.md](../web-app/README.md) 建立地圖、事件列表、插旗表單、通知 Banner 的 UI/UX 規格。
- 使用 browser Geolocation API 取得目前位置。
- 定期呼叫 Location Service 上傳位置。
- 更新使用者目前位置 marker，並顯示定位精度或 fallback 狀態。
- 建立事件發布表單，包含標題、內容、類型、嚴重程度。
- 在地圖上顯示事件標記。
- 收到 WebSocket 通知後，新增或更新事件 marker，點擊通知可移動到事件座標。
- 建立 WebSocket client，**實作斷線重連（reconnect with exponential backoff）與心跳監聽。**
- 收到緊急事件時顯示通知 Banner 或側邊事件卡片。
- **API 呼叫需補上基本錯誤處理（catch error、顯示提示訊息、不靜默失敗）。**

交付物：

- 可在瀏覽器執行的 Web App。
- 地圖頁面、事件表單、通知元件。
- UI/UX 檢查清單與 Demo 畫面截圖。
- 與三個後端服務的串接。

驗收標準：

- 使用者開啟 Web App 後可以看到地圖。
- 使用者允許定位後，前端會定期上傳座標。
- 使用者可以從 Web App 發布事件。
- 當附近有緊急事件時，Web App 會即時顯示通知。
- 手機寬度下，主要按鈕、事件卡片與通知 Banner 不會互相遮擋。

### 第 3 階段：即時資料與推播整合

目標：

- 確保 500 公尺區域推播邏輯正確。
- 讓多個 Notification Service Pod 也能處理 WebSocket 分散問題。

工作項目：

- 使用 Redis GEO 的 `GEOADD` 儲存使用者位置。
- 使用 Redis GEO 的 `GEOSEARCH` 查詢半徑內使用者，並用 last_seen TTL 過濾離線或過期使用者。
- Event Service 對每個附近使用者併發送出通知請求**（已改用 Redis Pub/Sub 解耦，Event Service 只做 PUBLISH，不再 HTTP fanout）。**
- **Event Service 已支援選填 `client_event_id` 去重，避免同一事件在 retry 時重複推播。**
- **Notification Service 已補上 WebSocket app-level ping/pong 心跳，偵測並清理已斷線的 ghost connection。**
- Notification Service 使用 Redis Pub/Sub 發布使用者專屬通知。
- 持有 WebSocket 連線的 Pod 訂閱對應 channel 並推送給前端。
- 補上事件 payload 格式與錯誤處理。

交付物：

- 500 公尺內使用者查詢流程。
- 多副本 Notification Service 可用的通知流程。
- 測試資料與測試指令。

驗收標準：

- 半徑內使用者會收到通知。
- 半徑外使用者不會收到通知。
- Notification Service 多副本時，通知仍能送到正確 WebSocket 連線。

### 第 4 階段：Kubernetes 與壓測

目標：

- 展示 K8s 的高併發處理、自動擴展與容錯能力。
- 讓專題 Demo 有明確技術亮點。

工作項目：

- 建立 Redis、Location Service、Event Service、Notification Service 的 K8s YAML。
- 為服務設定 resource requests 與 limits。
- 為 Location Service 設定 HPA。
- 為服務設定 readiness probe 與 liveness probe。
- 依照 [../system.md](../system.md) 規劃少量、中量、大量使用時的 resource requests/limits 與瓶頸處理方式。
- 建立 500-1,000 人虛擬使用者壓測腳本，保留 3,000 人進階參數。
- Demo 時觀察 Pod 數量變化與 HPA 狀態。
- Demo 時刪除一個 Notification Service Pod，觀察自動重建。
- 提供固定 PowerShell 腳本，降低 Demo 現場手動輸入錯誤。

交付物：

- `k8s/` 部署檔。
- `simulator/` 壓測腳本。
- `scripts/k8s-*.ps1` Demo 操作腳本。
- HPA 與 Pod 狀態截圖。

驗收標準：

- `kubectl apply -f k8s/` 可以部署系統。
- 壓測期間 Location Service Pod 會自動擴展。
- 刪除 Pod 後 Kubernetes 會自動補回副本。
- 系統在 Demo 過程中仍可處理位置更新與事件推播。

目前 repo 已完成第 4 階段所需的 YAML、HPA、resource requests/limits、readiness/liveness probes、壓測入口與 Demo 腳本。Docker Desktop Kubernetes 實測已完成：500 users / 60s cluster 內部壓測可觸發 Location Service HPA 擴展到 5 個 Pod，Notification Service Pod 刪除後可自動補回。**HPA 調優完成（8+8, targetCPU 30%, cpu request 100m），漸進式 300→3000 人壓測：有 HPA 在 3000 人維持 100% 成功率，無 HPA Event 0% 崩潰，圖表比較報告 `hpa_comparison.html` 已產出。**

### 跨階段工作：自動化測試

目標：

- 確保每次改動不會不小心破壞既有功能。
- 壓測之前先確認 API 行為正確，避免花時間除錯模擬腳本。

工作項目：

- 建立 `tests/` 目錄結構，對應三個服務（詳細測試案例請參考 [test-plan.md](./test-plan.md)）。
- Location Service 測試：`POST /locations` 寫入成功、`GET /locations/nearby` 正確查詢、參數邊界（緯度經度範圍）。
- Event Service 測試：`POST /events` 建立事件、附近查詢結果正確、通知推播呼叫符合預期。
- Notification Service 測試：WebSocket 連線與斷線、通知接收。
- 使用 `fakeredis` 或 docker-compose Redis 作為測試環境。
- 整合到 CI（選擇性，非專題必需品）。

交付物：

- `tests/` 測試目錄。
- 每個服務至少 2-3 個基本測試案例。
- 可透過 `pytest` 一次性執行所有測試。
- Web App 元件與 API client 測試。
- Docker Compose cross-service integration test 腳本。

驗收標準：

- `pytest` 通過所有 API 測試。
- 修改 API payload 後，測試會正確失敗提醒。
- `npm test` 通過 WebSocket client、事件表單、通知 Banner 與 API client 測試。
- `.\scripts\run-integration-tests.ps1` 可在 Docker Compose 環境驗證 Location → Redis → Event → Notification → WebSocket 完整鏈路。

### 第 5 階段：報告與展示整理

目標：

- 把技術成果轉成教授容易理解的展示內容。
- 每位組員都有清楚貢獻與可說明的技術點。

工作項目：

- 整理系統架構圖。
- 整理資料流圖。
- 整理 API 表格。
- 整理 K8s 部署圖。
- 整理壓測結果與截圖。
- 撰寫四人分工與心得。
- 準備 8 到 10 分鐘 Demo 腳本。

交付物：

- 專題簡報。
- 專題報告。
- Demo 腳本。
- GitHub repo。

驗收標準：

- 報告能清楚說明為什麼使用 Redis GEO、WebSocket 與 K8s。
- Demo 能在限制時間內完整展示日常情境與技術亮點。
- 每位成員都能說明自己的負責模組。

## 四人詳細分工

### 成員 A：Web App 與 UI/UX

主要責任：

- 建立 Web App 專案。
- 設計地圖主畫面。
- 實作事件插旗表單。
- 實作即時通知 Banner 或通知列表。
- 維護 UI/UX 檢查清單，確認地圖可讀性、定位權限、錯誤狀態與響應式布局。
- 串接 Location Service、Event Service 與 WebSocket。
- 與 B 確認 `POST /events` payload，與 C 確認 WebSocket notification JSON。

建議交付：

- `web-app/` 前端專案。
- UI/UX 設計規格與檢查清單。
- 地圖頁面截圖。
- 前端操作 Demo 影片或截圖。

報告可寫重點：

- 使用瀏覽器定位取得使用者位置。
- 使用地圖 UI 呈現空間資訊。
- 使用 WebSocket 達成即時通知體驗。

### 成員 B：後端 API 與事件邏輯

主要責任：

- 維護 Event Service。
- 定義事件 API payload。
- 實作事件建立、事件分類與嚴重程度。
- 呼叫 Redis GEO 查詢附近使用者。
- 呼叫 Notification Service 發送通知。
- 與 A 確認事件表單欄位，與 C 確認通知 payload 與 Redis GEO 查詢結果。

建議交付：

- Event Service API。
- API 文件與測試指令。
- 事件流程說明。

報告可寫重點：

- 微服務拆分與 API contract。
- 事件發布流程。
- 區域推播的商業邏輯。

### 成員 C：Redis 與即時推播

主要責任：

- 維護 Redis GEO key 與資料格式。
- 維護 Notification Service。
- 實作 WebSocket 連線管理。
- 實作 Redis Pub/Sub 通知同步。
- 測試半徑內與半徑外通知結果。
- 與 A 確認 WebSocket 斷線重連狀態，與 D 確認 Redis 與 Notification Service 多副本部署行為。

建議交付：

- Redis GEO 操作說明。
- WebSocket 推播流程。
- 500 公尺通知測試結果。

報告可寫重點：

- 為什麼即時位置適合放 Redis。
- Redis GEO 如何支援附近查詢。
- 多副本 WebSocket 服務如何透過 Pub/Sub 協作。

### 成員 D：DevOps、K8s 與壓測

主要責任：

- 撰寫 Dockerfile。
- 撰寫 Kubernetes YAML。
- 設定 HPA、resource requests、readiness probe。
- 撰寫 500-1,000 人壓測腳本，保留 3,000 人進階參數。
- 規劃 Demo 操作流程。
- 與全員確認 Demo 腳本、截圖備案與現場操作順序。

建議交付：

- `k8s/` 部署檔。
- `simulator/` 壓測腳本。
- HPA 擴展截圖。
- Pod 容錯截圖。

報告可寫重點：

- Kubernetes Deployment 與 Service。
- HPA 自動擴展。
- Pod failure recovery。
- 壓測如何模擬真實使用者流量。

## Demo 腳本（含時間分配）

本章節整理最後 Demo 的總體目標、成功標準、備案與實際操作順序。

Demo 要證明五件事：

1. 使用者可以在 Web App 地圖上查看目前位置與附近事件。
2. 使用者可以發布一般事件或緊急事件。
3. 緊急事件只會推播給 500 公尺內的使用者。
4. 系統可以承受 500-1,000 位虛擬使用者持續上傳 GPS 座標。
5. Kubernetes 可以在流量上升或 Pod 故障時維持服務可用。

一句話主軸：

```text
當校園中有人發布緊急事件時，系統會即時找出 500 公尺內的使用者並推播通知；同時後端可以透過 Kubernetes 面對大量座標更新與服務故障。
```

Demo 不追求正式會員註冊、正式上線、長期軌跡分析或原生手機 App。3,000 人壓測是進階挑戰，不是初期必要成功條件。

總長度 8-10 分鐘。每個步驟標註預計秒數。

| 時間 | 步驟 | 操作指令 | 展示重點 |
|------|------|----------|----------|
| 0:00-0:45 | 1. 開啟 Web App，說明校園即時地圖情境 | 打開瀏覽器 localhost 頁面 | 全螢幕地圖介面、專案動機 |
| 0:45-1:30 | 2. 瀏覽器定位，系統開始上傳位置 | 點擊「啟用定位」按鈕，允許權限 | browser Geolocation API、POST /locations |
| 1:30-2:15 | 3. 發布一般事件 | 點擊地圖 → 填寫表單（title, message, severity=info）→ 送出 → 地圖出現標記 | `POST /events`、事件插旗 UI |
| 2:15-3:00 | 4. 開啟第二個使用者，展示 WebSocket 連線 | 另開無痕視窗模擬不同使用者，打開瀏覽器 DevTools → Network → WS 確認連線 | WebSocket 連線狀態、ping/pong heartbeat、**CORS 已設定** |
| 3:00-4:00 | 5. 發布緊急事件，展示區域推播 | 發布 severity=urgent 事件，確認第二個使用者收到通知 Banner | Redis GEOSEARCH 500m 查詢、Redis Pub/Sub 推播 |
| 4:00-5:00 | 6. 啟動壓測腳本 | `python stress_test.py --users 500` | 大量座標更新流量、asyncio 併發；若本機效能允許可提高到 1,000 |
| 5:00-6:30 | 7. 展示 Docker Compose 資源監控 | 另一個 terminal 執行 `docker stats`，觀察各服務 CPU / 記憶體用量 | Docker Compose 容器資源使用、nginx 反向代理效能 |
| 6:30-7:30 | 8. 展示容器重啟容錯 | `docker compose restart notification-service`，觀察 WebSocket 自動重連與服務恢復 | Docker Compose 容器管理、WebSocket 重連機制 |
| 7:30-8:30 | 9. 總結技術亮點 | 展示壓測結果與架構圖 | Redis GEO 選型原因、微服務分工、Redis Pub/Sub 解耦優勢 |
| 8:30-10:00 | 10. Q&A 緩衝 | 無 | 回答教授問題 |

### Demo 注意事項

- **備案準備：** 提前截好 `docker stats` 資源監控截圖、容器重啟前後對比圖。萬一現場 Docker 環境異常，仍可展示截圖。可選展示 K8s HPA 擴展圖（若有 K8s 環境）。
- **網路風險：** 本機環境不使用外部 API，完全離線運作。確保 docker-compose 所有 image 已先 build 完成（`docker compose build`）。
- **指令腳本：** 建議將所有 docker compose 指令寫成 shell 腳本，避免現場打錯。
- **參數調整：** 本機壓測若 500 人不夠產生明顯負載，可提高到 1,000 人，或調整 stress_test.py 的 request interval。

## 十週進度表

以下為每週的詳細目標、負責人與驗收里程碑。總長度 10 週，階段之間允許部分重疊。

| 週次 | 階段 | 目標 | 負責人 | 週末驗收里程碑 |
|------|------|------|--------|----------------|
| 1 | 第 1 階段：後端骨架 | 建立三個微服務基本 API、shared 模組、Redis 連線 | B、C | `POST /locations` 可寫入 Redis；`GET /locations/nearby` 可查詢；WebSocket `/ws/{user_id}` 可連線 ✅ |
| 2 | 第 1 階段：後端骨架 | Dockerfile、docker-compose、CORS middleware、.dockerignore、healthz endpoint | D 主導，B、C 協助 | `docker compose up --build` 可啟動全部服務；API 可從不同 origin 呼叫 ✅（.dockerignore 待補） |
| 3 | 第 2 階段：Web App 啟動 | 決定地圖函式庫（Leaflet 優先建議）、建立 Vite/React 專案、全螢幕地圖顯示、瀏覽器定位 | A | 瀏覽器打開可看到地圖，允許定位後地圖上有使用者標記 |
| 4 | 第 2 階段：Web App API 串接 | 定期呼叫 Location Service 上傳座標、事件發布表單、地圖插旗 | A 主導，B 協助 API 規格 | 可從地圖點擊發布事件，標記顯示在地圖上 |
| 5 | 第 2 階段：WebSocket 通知 | WebSocket client 連線、斷線重連（exponential backoff）、通知 Banner/卡片 UI | A 主導，C 協助 WS 規格 | 收到緊急事件時前端即時顯示通知；網路斷開後自動重新連線 |
| 6 | 第 3 階段：即時推播整合 | 查詢 500m 附近使用者邏輯、Notification Service Pub/Sub 同步、多副本通知正確性 | C 主導，B 協助 | 半徑內使用者收到通知、半徑外不收；多副本時通知仍正確送達 |
| 6 | 第 3 階段：後端優化 | Event Service 已使用 asyncio.gather 批次推送、fan-out concurrency limit、選填 client_event_id 去重 | B | 500 人通知延遲 < 2 秒；retry 不重複推送 |
| 7 | 第 4 階段：K8s 部署 | 建置 Docker image、部署到 K8s、Service 設定、port-forward 測試、Demo 腳本 | D 主導，全員協助 | `.\scripts\k8s-deploy.ps1` 後所有 Pod Running；API 可透過 port-forward 呼叫 |
| 7 | 跨階段：自動化測試 | pytest + httpx.AsyncClient 基礎測試、fakeredis 測試環境 | B、C | `pytest` 通過 location-service 與 event-service 基本 API 測試 |
| 8 | 第 4 階段：HPA 與壓測 | metrics-server 啟用、HPA 設定、500-1,000 人壓測、觀察 Pod 自動擴展；3,000 人作為進階挑戰 | D 主導，全員協助 | `kubectl get hpa -w` 可看到 replica 有擴展跡象；壓測期間服務正常 |
| 8 | 跨階段：測試補齊 | Notification Service WebSocket 測試、前端 API 串接測試 | A、C | WebSocket 連線/斷線測試通過 |
| 9 | 第 5 階段：報告準備 | 架構圖、資料流圖、API 表格、K8s 部署圖、壓測截圖 | 全員 | 簡報初稿完成，包含所有圖表與截圖 |
| 10 | 第 5 階段：Demo 演練 | Demo 腳本演練、時間控制、Q&A 準備、備案確認 | 全員 | Demo 可在 8-10 分鐘內完整跑完 |

### 每週檢查點建議

- **週一早上的 Slack/Discord 訊息：** 每人一句本週目標。
- **週五下午的 15 分鐘線上會議：** 每人展示本週進度（螢幕分享），確認 milestone 是否達成。
- **若 milestone 未達成：** 下週優先補上，並評估是否影響 Demo 時間。

### 相依性注意

- 第 3 週（Web App 啟動）**不依賴** 第 2 週（docker-compose），可同時開始。
- 第 5 週（WebSocket 通知）**依賴** 第 2 週（Notification Service 可連線），若第 2 週延遲，A 可用 mock WebSocket server 先開發前端。
- 第 7 週（K8s 部署）**依賴** 第 2 週（Docker image），但 **不依賴** Web App 前端。
- 第 9-10 週（報告）**依賴** 第 8 週（壓測截圖），截圖需在第 8 週結束前完成。

## 風險與備案

風險：本機效能不足以穩定模擬 1,000 或 3,000 人。

備案：初期用 500 人展示流程，報告中說明參數可調；1,000 人作為初期進階目標，3,000 人作為最終挑戰或截圖補充。

風險：**Event Service HTTP fanout 在高併發下成為瓶頸。**

備案：已改用 Redis Pub/Sub 解耦，Event Service 只做 PUBLISH（微秒級），notification-service 訂閱後本地 geosearch + WS 推播。測試顯示 Event Service 成功率從 8.1% 提升到 100%（500 人壓測）。

風險：HPA 沒有擴展。

備案：確認 metrics-server 是否啟用，並調低 Location Service CPU request 或壓測 interval。

風險：瀏覽器定位權限被拒絕。

備案：提供手動選點或使用預設校園座標。

風險：WebSocket 多副本通知沒有命中正確 Pod。

備案：使用 Redis Pub/Sub，讓所有 Notification Service Pod 都能訂閱使用者通知 channel。

風險：Demo 網路不穩或 Docker/K8s 啟動過慢。

備案：提前準備截圖、錄影與已啟動環境，現場以短指令展示關鍵狀態。

風險：**CORS 未設定導致前端完全無法呼叫 API。**

備案：第一階段強制加入 CORS middleware，並在 docker-compose 中允許 `localhost:5173`（Vite dev server）與 `localhost:3000`（React dev server）。

風險：**Web App 開發時程延誤，Demo 無前端可用。**

備案：準備 curl/PowerShell 指令作為 API 展示備案，至少有 terminal 能展示後端功能。前端可先用最簡 HTML（無框架）確認 WebSocket 與 API 可通。

風險：**WebSocket 斷線重連未實作，Demo 時網路不穩導致使用者收不到通知。**

備案：前端的 WebSocket client 必須實作 reconnect with exponential backoff，避免一次斷線就永久失去連線。

風險：**Event Service 半徑查詢無使用者卻沒有錯誤提示。**

備案：確認附近查詢回傳空陣列時的處理流程，前端與後端都應有對應訊息提示。

## 整合會議建議

- 每週至少一次 15 分鐘同步 API 與 Demo 進度。
- 第 3 週開始固定確認 Web App 能否連到後端。
- 第 6 週開始固定確認 Redis GEO 與 WebSocket 完整鏈路。
- 第 8 週前完成第一版 HPA 截圖與 Pod 容錯截圖。
- 第 9 週開始只修 Demo 風險，不再加入大型新功能。
