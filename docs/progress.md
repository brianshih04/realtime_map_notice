# 專案進度追蹤表

本文件用來即時更新 `realtime_map_notice` 的開發進度。`project-plan.md` 是原始計畫，這份 `progress.md` 是目前實際狀態。

最後更新：2026-05-29
目前分支：`dev_K8s`
目前定位：第 7 週末 / 第 8 週初
整體進度估計：96%

## 狀態標記

| 標記 | 意義 |
|------|------|
| Done | 已完成並至少有基本驗證 |
| Partial | 已有實作，但仍缺整合測試、細節打磨或截圖 |
| Blocked | 因環境或相依條件卡住 |
| Pending | 尚未開始 |

## 總覽

| 階段 | 計畫週次 | 狀態 | 完成度 | 目前證據 | 下一步 |
|------|----------|------|--------|----------|--------|
| 第 1 階段：後端骨架 | 1-2 | Done | 95% | 三個 FastAPI service、shared module、Dockerfile、docker-compose、CORS、`.dockerignore` 已存在；`docker compose up --build -d` 已實測成功 | 補更完整的跨服務自動化測試 |
| 第 2 階段：Web App 前端 | 3-5 | Partial | 84% | React + Vite + Leaflet 可 build，地圖 smoke test 可開啟；WebSocket client、EventForm、NotificationBanner 與 API client 已有 Vitest 測試 | 串接真實後端服務並做瀏覽器端完整流程 QA |
| 第 3 階段：即時資料與推播整合 | 4-6 | Done | 94% | Redis GEO、last_seen 過濾、WebSocket Pub/Sub、pong timeout heartbeat、fan-out limit、client_event_id 去重已實作；Docker Compose cross-service 完整鏈路與 WebSocket no-cross-talk 測試已通過 | 保存 Demo 截圖，後續可補 K8s 多副本 WebSocket 實測 |
|| 第 4 階段：Kubernetes 與壓測 | 6-8 | Done | 98% | Docker Compose 已可跑；Docker Desktop Kubernetes 已 Ready；K8s 實機部署成功；metrics-server 已可提供 CPU 指標；500 人 cluster 內部壓測已觸發 HPA 擴到 5 個 Pod；Notification Pod 刪除後可自動補回；**HPA 調優完成（8+8, targetCPU 30%）；漸進式 300→3000 人壓測完成，有 HPA 在 3000 人維持 100%，無 HPA 崩潰至 0%**；圖表比較報告已產出 | 整理截圖，補簡報素材 |
| 跨階段：自動化測試 | 7-8 | Partial | 56% | `tests/requirements-test.txt` 已補齊 FastAPI/Redis 測試相依；後端 unit + API/WebSocket contract tests 31 個通過；前端 Vitest 4 個通過 | 補真實 Redis、更多前端元件測試 |
| 第 5 階段：報告與展示整理 | 8-10 | Partial | 32% | project-plan、system、demo 腳本初稿已存在；已補 Cloudflare Tunnel 對外入口規劃 | 產出實測截圖、壓測數據、Demo 錄影或備案素材 |

## 必做功能進度

| 功能 | 狀態 | 完成度 | 備註 |
|------|------|--------|------|
| Web App 顯示地圖 | Done | 90% | Leaflet + OpenStreetMap 已可顯示；仍需更多 responsive QA |
| 使用者在地圖發布事件 | Partial | 78% | 前端表單與 Event Service 已有；Docker Compose 環境下 Event API smoke test 通過 |
| 使用者位置定期上傳 | Partial | 82% | 前端定時上傳、後端 `POST /locations` 已有；Docker Compose 環境下 Redis 寫入與附近查詢 smoke test 通過 |
| 地圖 marker 隨資料更新 | Partial | 70% | local events 與 WS events 可顯示；仍需真實後端測試 |
| Redis GEO 即時位置 | Partial | 88% | GEOADD/GEOSEARCH 與 last_seen 過濾已實作；Docker Compose 實體 Redis smoke test 通過 |
| 500 公尺區域通知 | Done | 92% | Event Service 查 nearby + 通知 active users 已實作；Docker Compose cross-service 測試確認附近使用者收到、遠端使用者不在 delivered_to |
| WebSocket 主動推播 | Done | 94% | Pub/Sub + WebSocket + pong timeout heartbeat 已實作；後端 route contract、前端 WebSocket client、Docker Compose cross-service no-cross-talk 測試均通過 |
| 500-1,000 人 simulator | Partial | 85% | 本機 simulator 支援固定 duration、timeout 與成功/失敗統計；cluster 內部 Job 可避免 port-forward 瓶頸；500 人壓測已成功 | 尚未跑 1,000 人測試與長時間穩定性測試 |
|| K8s Location Service HPA | Done | 100% | metrics-server 可讀 CPU；HPA 調優完成（maxReplicas 8, targetCPU 30%, cpu request 100m）；漸進式 300→3000 人壓測：有 HPA 在 3000 人維持 100% 成功率，無 HPA Event 0% 崩潰；圖表比較報告 `hpa_comparison.html` 已產出 | 保存截圖，放入簡報 |
| K8s Notification Pod 容錯 | Done | 95% | 多副本 YAML 與刪 Pod 腳本已存在；實測刪除 Pod 後 Deployment 自動補回至 3/3 Running | 保存 Demo 截圖 |

## 測試與驗證

| 類別 | 狀態 | 最近結果 | 缺口 |
|------|------|----------|------|
| Python unit tests | Done | `python -m pytest tests/unit -q`，23 passed | 尚未加入 coverage 報告 |
| API contract tests | Partial | `python -m pytest tests/integration -q`，4 passed | 尚未使用真實 Redis / docker-compose |
| Python syntax check | Done | `python -m py_compile ...` 通過 | 無 |
| Frontend lint | Done | `npm run lint` 通過 | 無 |
| Frontend build | Done | `npm run build` 通過 | 無 |
| Frontend unit tests | Partial | `npm test`，15 passed | 尚未補 Map 元件與 App 整合測試 |
| Web App smoke test | Done | `http://127.0.0.1:5173` 可開，地圖載入 | 仍需串後端 |
| Docker Compose | Done | `.\scripts\compose-smoke-test.ps1` 通過，Redis + 三個 FastAPI services 均 healthy，位置/nearby/event fan-out/idempotency 均驗證 | 無 |
| API integration tests | Done | `python -m pytest tests -q` 通過；Docker Compose cross-service 測試 2 passed | 可選補更多邊界案例 |
| WebSocket integration tests | Done | heartbeat pong timeout unit tests、`/ws/{user_id}` route contract test、cross-service WebSocket no-cross-talk 測試通過 | 可選補 K8s 多副本 WebSocket 實測 |
| K8s deployment test | Done | `.\scripts\k8s-build-images.ps1`、`.\scripts\k8s-deploy.ps1`、port-forward health check 均成功；Redis 1、Location 1、Event 2、Notification 3 全部 Running | 尚需保存 Demo 截圖 |
| K8s metrics-server | Done | `.\scripts\k8s-install-metrics-server.ps1` 成功；`kubectl top nodes` 與 `kubectl top pods -n realtime-map-notice` 可顯示 CPU / memory；HPA 顯示 `cpu: 2%/60%` | 尚需壓測時觀察 HPA 擴展 |
|| Load test | Done | `scripts/k8s-load-test.ps1` 與 `scripts/k8s-load-test-job.ps1` 已建立；500 users / 60s cluster 內部壓測成功並觸發 HPA；**漸進式 300→3000 人壓測完成，HPA 8+8 targetCPU 30% 調優，有 HPA 3000 人 100% 成功率，圖表比較 `hpa_comparison.html` 已產出** | 截圖放入簡報 |

## 目前阻塞

| 阻塞 | 影響 | 解法 | 優先級 |
|------|------|------|--------|
| 目前無阻塞 | — | — | — |

## 接下來建議工作順序

| 順序 | 工作 | 預期產出 | 負責角色 |
|------|------|----------|----------|
| 1 | 補真實 Redis / Notification integration tests | Redis GEO、Pub/Sub、Notification API 基礎整合測試 | B、C |
| 2 | 手動測完整資料流 | Web App 位置寫入、事件建立、WebSocket 通知成功 | A、B、C |
| 3 | Demo 演練與報告素材整理 | 8-10 分鐘 Demo 可跑完 | 全員 |

## 更新紀錄

| 日期 | 更新內容 | 驗證 |
|------|----------|------|
| 2026-05-29 | HPA 壓測完成：漸進式 300→3000 人，有 HPA 3000 人 100% 成功率、無 HPA Event 0% 崩潰；HPA 調優（8+8, targetCPU 30%, cpu request 100m）；圖表比較 `hpa_comparison.html` 已產出；所有文件加入 HPA 內容 | 壓測 JSON 數據 + Chart.js 圖表 |
| 2026-05-28 | 全面更新文件以反映 Redis Pub/Sub 架構變更與最新功能狀態 | 文件更新 |
| 2026-05-27 | 執行 Docker Compose cross-service integration，驗證 Location → Redis → Event → Notification → WebSocket 完整鏈路與 WebSocket no-cross-talk；修正 integration 腳本清理 orphan containers | `.\scripts\run-integration-tests.ps1`，2 passed |
| 2026-05-26 | 建立 Cloudflare 對外入口骨架，使用 `map.avision-gb10.org`、edge proxy、cloudflared config 範本與前端正式環境變數 | 文件與設定檔更新；尚未建立實際 Tunnel credentials |
| 2026-05-26 | 補強第 2、3 階段：新增前端 EventForm、NotificationBanner、Location/Event API client 測試；新增 Docker Compose cross-service integration test 腳本與完整鏈路/WebSocket no-cross-talk 測試檔 | `npm test` 15 passed；`npm run lint`、`npm run build` 通過；`python -m pytest tests -q` 31 passed, 1 skipped |
| 2026-05-26 | 新增 simulator 固定時間、timeout、成功/失敗統計；新增 cluster 內部 K8s load test Job，避免 port-forward 壓測瓶頸；完成 500 users / 60s HPA 實測 | `success=12331 failed=3`；HPA `cpu: 259%/60%`；Location Service 擴到 5 Pods |
| 2026-05-26 | 修正 Notification Pod 容錯 Demo 腳本，刪除 Pod 後等待 Deployment rollout 完成並自動退出；完成 Pod 自動補回實測 | `notification-service` 刪除 1 Pod 後自動回到 `3/3 Running` |
| 2026-05-26 | 修正 K8s 部署腳本，改為先建立 namespace 再依序套用服務，避免首次部署 race；新增 metrics-server 安裝腳本並完成 Docker Desktop Kubernetes 實測 | `.\scripts\k8s-deploy.ps1` 成功；`.\scripts\k8s-install-metrics-server.ps1` 成功；HPA 顯示 `cpu: 2%/60%` |
| 2026-05-26 | 新增後續公開入口需求：註冊網域、Cloudflare DNS/Tunnel、反向代理或 K8s Ingress，整理單一公開網址與 WebSocket 路由 | 文件更新 |
| 2026-05-26 | Docker Desktop Kubernetes 後續自動完成初始化，`docker-desktop` context 已建立，control plane 與 system pods Running | `kubectl cluster-info` 成功；`kubectl get nodes -o wide` 顯示 `desktop-control-plane` Ready |
| 2026-05-26 | 診斷 Docker Desktop Kubernetes：設定已啟用，但 kubeconfig 仍為空；Docker logs 顯示 kind control-plane 初始化後 `Timed out waiting for Ready`，尚未可用 | `kubectl config get-contexts` 無 context；`kubectl cluster-info` 仍連 localhost:8080 |
| 2026-05-26 | 新增 Docker Compose smoke test 腳本，可自動啟動 compose 並驗證 healthz、位置寫入、附近查詢、urgent event fan-out 與 `client_event_id` 去重 | `.\scripts\compose-smoke-test.ps1` 通過 |
| 2026-05-26 | Docker Desktop 安裝完成，Docker CLI/Compose/kubectl CLI 可用；Docker Compose 實機建置並啟動 Redis + 三個後端服務；完成 healthz、位置寫入、附近查詢、urgent event fan-out smoke test | `docker compose up --build -d` 成功；三個 `/healthz` 回 `ok`；Event API `delivered_count=2` |
| 2026-05-26 | 新增前端 Vitest 測試，覆蓋 WebSocket client 連線路徑、ping/pong、通知解析與斷線重連 | `npm test` 4 passed；`npm run lint`、`npm run build` 通過 |
| 2026-05-26 | 新增 WebSocket route contract test，驗證 `/ws/{user_id}` 會把 Redis Pub/Sub 訊息推到前端；修正正常斷線時 background task 的清理例外 | `python -m pytest tests -q` 31 passed |
| 2026-05-26 | 強化 Notification Service heartbeat：前端 pong 會刷新狀態，超過 timeout 會關閉 stale WebSocket；補 Notification API 與 heartbeat unit tests | `python -m pytest tests -q` 30 passed |
| 2026-05-26 | 新增第一批 API contract tests，覆蓋 Location API 位置上傳/附近查詢/座標驗證，以及 Event API 只通知 active nearby users | `python -m pytest tests -q` 26 passed |
| 2026-05-26 | 補齊測試相依，讓後端 unit tests 可在乾淨 clone 後重現執行；重新安裝前端相依並校正 lockfile 專案名稱 | `python -m pytest tests/unit -q` 23 passed；`npm run lint`、`npm run build` 通過 |
| 2026-05-26 | 新增 Event Service fan-out concurrency limit 與選填 `client_event_id` 去重 | 23 unit tests、frontend lint/build 通過 |
| 2026-05-26 | 完成第 4 階段 repo 交付物：K8s probes/resources/env、HPA、壓測與 Demo 腳本、K8s 文件 | unit tests、frontend lint/build、Markdown 連結檢查通過；Docker/K8s 實機待環境可用 |
| 2026-05-26 | 擴充後端 unit tests，涵蓋 schema、active user 過濾、event handler、notification helper | 17 unit tests 通過 |
| 2026-05-25 | 改善即時通知流程：Event fan-out 併發、WebSocket heartbeat、last_seen 過濾 | unit tests、frontend lint/build 通過 |
| 2026-05-25 | 建立 Web App React + Vite + Leaflet 基礎 | frontend lint/build 通過 |
| 2026-05-25 | 擴充 `CLAUDE.md` agent 指引 | 文件提交至 dev |

## 每次更新檢查清單

- 更新「最後更新」日期。
- 更新階段總覽的狀態與完成度。
- 若完成或新增測試，更新「測試與驗證」。
- 若遇到環境問題，更新「目前阻塞」。
- 若完成重要功能，新增一筆「更新紀錄」。
- 若進度影響 Demo 腳本或架構描述，同步更新 [project-plan.md](./project-plan.md)、[../system.md](../system.md) 或 [../development.md](../development.md)。
