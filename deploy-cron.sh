#!/bin/bash
# CI/CD 自動部署腳本
# 由 crontab 每 2 分鐘執行，偵測 GitHub 上是否有新 commit，自動 pull 並部署
# Usage: ./deploy-cron.sh [docker|k8s]

set -euo pipefail

REPO_DIR="/home/avuser/realtime_map_notice"
LOCK_FILE="/tmp/deploy-cron.lock"
LOG_FILE="/tmp/deploy-cron.log"

exec >> "$LOG_FILE" 2>&1

# 防止重複執行
exec 200>"$LOCK_FILE"
flock -n 200 || exit 0

cd "$REPO_DIR"

MODE="${1:-docker}"
BRANCH=$(git branch --show-current)

# 決定要追蹤的遠端分支
if [ "$MODE" = "k8s" ]; then
    TARGET_BRANCH="dev_K8s"
    CURRENT_BRANCH=$(git branch --show-current)
    if [ "$CURRENT_BRANCH" != "$TARGET_BRANCH" ]; then
        git checkout "$TARGET_BRANCH" 2>/dev/null || true
    fi
else
    TARGET_BRANCH="dev"
    CURRENT_BRANCH=$(git branch --show-current)
    if [ "$CURRENT_BRANCH" != "$TARGET_BRANCH" ]; then
        git checkout "$TARGET_BRANCH" 2>/dev/null || true
    fi
fi

# Fetch 並比對是否有新 commit
git fetch origin "$TARGET_BRANCH" --quiet
LOCAL_SHA=$(git rev-parse HEAD)
REMOTE_SHA=$(git rev-parse "origin/$TARGET_BRANCH")

if [ "$LOCAL_SHA" = "$REMOTE_SHA" ]; then
    exit 0  # 沒有新 commit
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') — [$MODE] New commit detected: $REMOTE_SHA (was $LOCAL_SHA)"

# Pull
git pull origin "$TARGET_BRANCH" --quiet

# 部署
if [ "$MODE" = "k8s" ]; then
    echo "Deploying to Kubernetes..."
    kubectl apply -f k8s/namespace.yaml
    kubectl apply -f k8s/redis.yaml
    kubectl apply -f k8s/nginx-configmap.yaml
    kubectl apply -f k8s/location-service.yaml
    kubectl apply -f k8s/event-service.yaml
    kubectl apply -f k8s/notification-service.yaml
    kubectl apply -f k8s/web.yaml
    echo "Kubernetes deployment complete."
else
    echo "Deploying with Docker Compose..."
    docker compose up --build -d
    echo "Docker Compose deployment complete."
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') — [$MODE] Deployment done."
