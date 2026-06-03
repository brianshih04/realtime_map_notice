# 文件導覽

這個資料夾保留專題補充文件。整理後，文件數量已減少，較常閱讀的內容合併到根目錄文件與子系統 README 中。

## 建議閱讀順序

1. [../readme.md](../readme.md)

   先看專案總覽、使用情境、技術選型與目前狀態。

2. [../system.md](../system.md)

   看系統架構、API contract、Redis 設計、即時位置、容量規劃、瓶頸與 K8s 展示重點。

3. [project-plan.md](./project-plan.md)

   看十週計畫、Demo 目標、四人分工、風險與備案。

4. [test-plan.md](./test-plan.md)

   看後端、前端、WebSocket、跨服務整合與 E2E 測試規劃。

5. [part-c-redis-geo-websocket.md](./part-c-redis-geo-websocket.md)

   看成員 C 的 Redis GEO、WebSocket、附近推播責任邊界、API 與 Demo 步驟。

6. [part-c-test-plan.md](./part-c-test-plan.md)

   看成員 C 的獨立測試計畫、手動測試案例、驗收標準與 Demo 前檢查清單。

7. [../development.md](../development.md)

   看本機開發、API 測試、壓測與 K8s Demo 操作流程。

8. [../k8s/README.md](../k8s/README.md)

   看 Kubernetes 部署、HPA、Pod 容錯與常見問題。

9. [../web-app/README.md](../web-app/README.md)

   看前端專案建議結構、地圖服務、UI/UX、API key 與環境變數。

## 文件用途對照

| 文件 | 適合誰看 | 主要用途 |
|------|----------|----------|
| `readme.md` | 全員、教授 | 快速理解專題做什麼 |
| `system.md` | 後端、資料庫、DevOps | 架構、API、即時位置、容量與瓶頸 |
| `docs/project-plan.md` | 全員 | 十週進度、Demo 目標、四人分工與風險 |
| `docs/test-plan.md` | 前端、後端 | 測試策略與案例 |
| `docs/part-c-redis-geo-websocket.md` | 成員 C | Redis GEO、WebSocket、附近推播與 Demo 步驟 |
| `docs/part-c-test-plan.md` | 成員 C | 獨立測試計畫、手動測試案例與驗收標準 |
| `development.md` | 開發者 | 本機啟動與測試指令 |
| `k8s/README.md` | DevOps | Kubernetes 操作 |
| `web-app/README.md` | 前端 | 前端實作方向、地圖服務、UI/UX、API key |

## 已合併的文件

為了減少文件分散，以下內容已合併：

- `architecture.md` -> [../system.md](../system.md)
- `capacity-and-bottlenecks.md` -> [../system.md](../system.md)
- `realtime-location-requirements.md` -> [../system.md](../system.md)
- `demo-goals.md` -> [project-plan.md](./project-plan.md)
- `team-plan.md` -> [project-plan.md](./project-plan.md)
- `ui-ux-guidelines.md` -> [../web-app/README.md](../web-app/README.md)
- `external-services-and-secrets.md` -> [../web-app/README.md](../web-app/README.md)

## 維護規則

- 文件檔名維持小寫，除子資料夾的 `README.md` 外，根目錄使用 `readme.md`、`development.md`、`system.md`。
- 新增文件前，先判斷是否能放進既有文件，避免再次分散。
- 如果架構、API 或位置資料欄位改動，請同步更新 [../system.md](../system.md) 與 [test-plan.md](./test-plan.md)。
- 如果 Demo 目標或流程改動，請同步更新 [project-plan.md](./project-plan.md) 與 [../development.md](../development.md)。

