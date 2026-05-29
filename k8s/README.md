# Kubernetes 使用方式

這份文件描述如何把 `realtime_map_notice` 的後端服務部署到 Kubernetes，並展示 HPA 自動擴展與 Pod 容錯。所有指令預設在專案根目錄執行。

少量、中量、大量使用時的 resource 調整與瓶頸分析，請參考 [../system.md](../system.md)。

## 前置需求

- Docker Desktop Kubernetes 或 minikube。
- `kubectl` 已連到正確 cluster。
- metrics-server 已安裝或啟用，否則 HPA 會顯示 `<unknown>`。
- 已在本機建立三個服務的 Docker image。

確認目前 cluster：

```powershell
kubectl config current-context
kubectl get nodes
```

安裝 metrics-server：

```powershell
.\scripts\k8s-install-metrics-server.ps1
```

若是在正式 cluster，且不需要本機 kubelet TLS workaround，可以改用：

```powershell
.\scripts\k8s-install-metrics-server.ps1 -SkipInsecureTlsPatch
```

## 建立本機 Image

若使用 Docker Desktop Kubernetes：

```powershell
.\scripts\k8s-build-images.ps1
```

若使用 minikube，先執行：

```powershell
.\scripts\k8s-build-images.ps1 -LoadToMinikube
```

## 部署

```powershell
.\scripts\k8s-deploy.ps1
```

部署腳本會先建立 namespace，再依序套用 Redis、Notification Service、Location Service 與 Event Service，避免第一次部署時 namespace 尚未可用造成部分 manifest 失敗。

等待所有 Pod 就緒：

```powershell
kubectl -n realtime-map-notice wait --for=condition=Ready pod --all --timeout=180s
```

查看服務：

```powershell
.\scripts\k8s-status.ps1
```

## Port Forward

```powershell
.\scripts\k8s-port-forward.ps1
```

建議分三個 PowerShell 視窗分別執行 port-forward，避免單一終端機被阻塞後不好操作。

健康檢查：

```powershell
.\scripts\k8s-health-check.ps1
```

## 500-1,000 人壓測

先確認已經執行 port-forward，讓本機 `http://localhost:8001` 可以連到 K8s 中的 Location Service。

初期 Demo 目標：

```powershell
.\scripts\k8s-load-test.ps1 -Users 500 -Interval 1
```

若要固定跑一段時間後自動停止：

```powershell
.\scripts\k8s-load-test.ps1 -Users 500 -Interval 1 -DurationSeconds 60
```

`k8s-load-test.ps1` 會透過本機 port-forward 打進 K8s，適合小流量 smoke test。若要展示 HPA，建議改用 cluster 內部 Job，避免 port-forward 先成為瓶頸：

```powershell
.\scripts\k8s-load-test-job.ps1 -Users 500 -Interval 1 -DurationSeconds 60 -TimeoutSeconds 5
```

目前實測結果：500 users / 60s cluster 內部壓測完成 `success=12331 failed=3`，HPA 最高觀察到 `cpu: 259%/60%`，Location Service 從 1 個 Pod 擴展到 5 個 Pod。

進階目標：

```powershell
.\scripts\k8s-load-test.ps1 -Users 1000 -Interval 1
```

若需要觀察極限或準備截圖，可再嘗試：

```powershell
.\scripts\k8s-load-test.ps1 -Users 3000 -Interval 1
```

壓測時建議同時開另一個 PowerShell 視窗：

```powershell
kubectl -n realtime-map-notice get hpa -w
kubectl -n realtime-map-notice get pods -w
```

## 觀察 HPA

```powershell
kubectl -n realtime-map-notice get hpa -w
```

HPA 需要 metrics-server。若 HPA 顯示 unknown，請先安裝或啟用 metrics-server。

壓測時可以同時觀察：

```powershell
kubectl -n realtime-map-notice get pods -w
kubectl -n realtime-map-notice top pods
kubectl -n realtime-map-notice describe hpa location-service-hpa
```

### HPA 壓測結果

使用漸進式壓測腳本（300→3000→300 用戶），HPA 配置：maxReplicas 8、targetCPU 30%、cpu request 100m。

| 並發用戶 | 無 HPA Location | 無 HPA Event | 有 HPA Location | 有 HPA Event | Pods（有HPA） |
|----------|-----------------|--------------|-----------------|--------------|---------------|
| 300 | 100% | 100% | 100% | 100% | 4 / 1 |
| 800 | 99.5% | 99.9% | **100%** | **100%** | 8 / 2 |
| 1500 | 93.2% | 95.5% | **99.1%** | **98.5%** | 8 / 2 |
| 2000 | 83.9% | 78.5% | **98.1%** | **99.9%** | 8 / 3 |
| 3000 | 94.8% | **0%** ❌ | **100%** | **100%** | 8 / 3 |

**關鍵發現**：有 HPA 在 3000 人並發下仍維持 100% 成功率，無 HPA 在 3000 人時 Event Service 完全崩潰。

完整圖表比較報告見 `hpa_comparison.html`。

### HPA 參數調優

- **CPU request 5m→100m**：原始 5m 導致 idle CPU 就佔 60%，HPA 永遠誤判需擴展。修正後 idle 只佔 3-5%。
- **targetCPU 50%→30%**：30% 讓 HPA 更早觸發擴展，Pod 數量更充足，在高併發下成功率更好。
- **maxReplicas 8+6→8+8**：Location 與 Event 兩個服務統一為 8 個 Pod 上限，符合 minikube 20 CPU 資源限制。

## Pod 容錯 Demo

刪除一個 Notification Service Pod：

```powershell
.\scripts\k8s-delete-notification-pod.ps1
```

觀察 Kubernetes 自動補回：

```powershell
kubectl -n realtime-map-notice get pods -w
```

預期結果：

- 被刪除的 Pod 進入 Terminating。
- ReplicaSet 建立新的 Pod。
- 新 Pod 從 Pending 變成 Running。
- Service 仍保留穩定 DNS 名稱 `notification-service`。

## 第四階段 Demo 截圖清單

建議至少準備下列截圖，避免現場網路或 K8s 環境不穩時沒有備案：

| 截圖 | 指令 |
|------|------|
| 所有 Pod Running | `kubectl -n realtime-map-notice get pods -o wide` |
| Service 與 HPA | `kubectl -n realtime-map-notice get svc,hpa` |
| HPA 擴展前 | `kubectl -n realtime-map-notice get hpa` |
| HPA 擴展中 | `kubectl -n realtime-map-notice get hpa -w` |
| Pod 容錯前 | `kubectl -n realtime-map-notice get pods` |
| 刪除 Notification Pod 後自動重建 | `.\scripts\k8s-delete-notification-pod.ps1` |

## 第四階段完成條件

Repo 交付物已包含：

- Redis、Location Service、Event Service、Notification Service 的 K8s YAML。
- Location Service HPA。
- 所有服務的 resource requests/limits。
- Redis、Location Service、Event Service、Notification Service 的 readiness/liveness probe。
- 500-1,000 人壓測腳本入口。
- Pod 容錯 Demo 腳本。
- HPA / Pod / Service 觀察指令。

實機完成條件：

- `.\scripts\k8s-build-images.ps1` 成功。
- `.\scripts\k8s-install-metrics-server.ps1` 成功，且 `kubectl top nodes` 可顯示指標。
- `.\scripts\k8s-deploy.ps1` 成功，所有 Pod Running。
- `.\scripts\k8s-port-forward.ps1` 後 `.\scripts\k8s-health-check.ps1` 成功。
- `.\scripts\k8s-load-test.ps1 -Users 500` 可執行，HPA 有擴展跡象。
- `.\scripts\k8s-delete-notification-pod.ps1` 後 Kubernetes 自動補回 Pod。

## 常見問題

### HPA 顯示 unknown

可能原因：

- metrics-server 尚未啟用。
- Pod 沒有設定 CPU requests。
- metrics-server 無法讀取 node 指標。

先檢查：

```powershell
kubectl top nodes
kubectl top pods -n realtime-map-notice
```

### Pod 一直 ImagePullBackOff

可能原因：

- 本機 image 名稱與 YAML 不一致。
- minikube 沒有載入本機 image。
- `imagePullPolicy` 設定導致 cluster 嘗試從遠端 registry 拉 image。

檢查：

```powershell
kubectl -n realtime-map-notice describe pod <pod-name>
```

### Service 無法連線

可能原因：

- Pod 尚未 Ready。
- port-forward 指令未執行。
- Service selector 與 Pod label 不一致。

檢查：

```powershell
kubectl -n realtime-map-notice get endpoints
kubectl -n realtime-map-notice describe svc location-service
```
