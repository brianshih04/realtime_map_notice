# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

`realtime_map_notice` is a real-time campus map notification system using microservices (FastAPI), Redis GEO, and WebSocket. The codebase and documentation are bilingual (Traditional Chinese and English). Users post map markers (events) that trigger location-based notifications to nearby users (within 500m).

## Build & Run

```bash
docker compose up --build          # 啟動全部（Redis + 3 services）
docker compose up --build -d       # 背景啟動
docker compose logs -f <service>   # 看日誌
docker compose down                # 停掉
```

Services bind to host ports 8001/8002/8003 (internal: 8000).

## Local Development

```bash
# Set up environment (copy from .env.example)
cp .env.example .env

# Optional: Python virtual environment for simulator/scripts
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .\.venv\Scripts\Activate.ps1  # Windows PowerShell

# Install simulator dependencies
pip install -r simulator/requirements.txt
```

### API Documentation

Each FastAPI service has interactive API docs:
- Location Service: http://localhost:8001/docs
- Event Service: http://localhost:8002/docs
- Notification Service: http://localhost:8003/docs

## Test

```bash
# 目前沒有 tests/，尚未實作。建立測試時：
pytest                              # 跑全部
pytest tests/unit/                  # 只跑 unit
pytest tests/integration/           # 需先 docker compose up
```

## Architecture

```
Web App → Location Service (:8001) → Redis GEO
Web App → Event Service (:8002) → Redis GEOSEARCH → Notification Service (:8003) → Redis Pub/Sub → WebSocket → Web App
```

Three independent FastAPI services share `backend/shared/` (schemas, config, redis_client, cors). Each has its own Dockerfile. Redis is the only stateful dependency.

## Service Entrypoints

| Service | Host Port | Internal | Main File |
|---------|-----------|----------|-----------|
| Location Service | 8001 | 8000 | `backend/location-service/app/main.py` |
| Event Service | 8002 | 8000 | `backend/event-service/app/main.py` |
| Notification Service | 8003 | 8000 | `backend/notification-service/app/main.py` |

## Code Conventions

- **PYTHONPATH=/app** inside Docker. All imports use `from backend.shared import ...`.
- Folder names use hyphens (`location-service`), NOT underscores. Cannot do normal Python import from these paths — use `importlib` if importing outside Docker.
- Pydantic v2 models live in `backend/shared/schemas.py`. Add new fields there.
- Redis client factory: `backend/shared/redis_client.py` → `create_redis()`.
- CORS config: `backend/shared/cors.py` → reads `CORS_ALLOW_ORIGINS` env var.
- Each service: `backend/<service>/app/main.py` is the FastAPI app entrypoint.
- Dockerfile copies `backend/shared` then `backend/<service>/app` into `/app/`.

## Env Vars

| Var | Default | Where |
|-----|---------|-------|
| `REDIS_URL` | `redis://localhost:6379/0` | shared/config.py |
| `USER_LOCATION_KEY` | `realtime_map_notice:user:locations` | shared/config.py |
| `USER_LAST_SEEN_PREFIX` | `realtime_map_notice:user:last_seen` | shared/config.py |
| `DEFAULT_ALERT_RADIUS_METERS` | `500` | shared/config.py |
| `CORS_ALLOW_ORIGINS` | `http://localhost:5173,http://localhost:3000` | shared/config.py |
| `NOTIFICATION_SERVICE_URL` | `http://localhost:8003` | event-service only |

## Gotchas

- `.dockerignore` doesn't exist yet — `.git` and `__pycache__` bloat build context. Create one if editing Dockerfiles.
- Event Service notifies nearby users one-by-one (`async for` loop). For 500+ users this is slow. Use `asyncio.gather` or bypass HTTP via direct Redis Pub/Sub.
- No WebSocket heartbeat — disconnected clients leave ghost connections.
- No test suite exists yet. See `docs/test-plan.md` for planned test structure.
- `web-app/` is empty (only a README). Frontend is not implemented.
- No `.env` file tracked — copy from `.env.example`.

## K8s

```bash
# Build images first (no CI/CD pipeline)
docker build -t realtime-map-notice/location-service:latest -f backend/location-service/Dockerfile .
docker build -t realtime-map-notice/event-service:latest -f backend/event-service/Dockerfile .
docker build -t realtime-map-notice/notification-service:latest -f backend/notification-service/Dockerfile .

kubectl apply -f k8s/
kubectl -n realtime-map-notice get pods -w
kubectl -n realtime-map-notice get hpa -w
```

Namespace: `realtime-map-notice`. Location Service has HPA (1–5 replicas, CPU 60%). Event/Notification: 2+ replicas.

## Load Testing

```bash
python simulator/simulate_users.py --users 500 --target http://localhost:8001 --interval 1
# Advanced: --users 3000
```

Requires: `pip install -r simulator/requirements.txt`

## Additional Documentation

- `readme.md` - Project overview, goals, and technology choices
- `development.md` - Detailed development workflow and demo procedures
- `system.md` - System architecture, API contracts, capacity planning
- `docs/project-plan.md` - 10-week development timeline and milestones
- `docs/test-plan.md` - Planned test structure (not yet implemented)
- `k8s/README.md` - Kubernetes deployment and fault tolerance demos
- `web-app/README.md` - Frontend development directions (not yet implemented)
