# CLAUDE.md

## Build & Run

```bash
docker compose up --build          # 啟動全部（Redis + 3 services）
docker compose up --build -d       # 背景啟動
docker compose logs -f <service>   # 看日誌
docker compose down                # 停掉
```

Services bind to host ports 8001/8002/8003 (internal: 8000).

### Web App

```bash
cd web-app
npm install
npm run dev         # Vite dev server on :5173
npm run build       # production build → dist/
```

## Test

```bash
# Backend (no docker needed)
pytest tests/unit/ -v                     # 21 unit tests
pytest tests/integration/ -v              # 19 integration tests (fakeredis)
pytest tests/unit/ tests/integration/ -v  # 40 tests total (~0.8s)

# Cross-service integration (requires docker compose up -d)
./scripts/run-integration-tests.ps1       # or: pytest tests/integration/cross_service/ -v --timeout=30

# Frontend
cd web-app && npm test                    # 21 tests (Vitest)
```

Cross-service tests require docker-compose running. All other tests use fakeredis/mocks and run instantly.

## Architecture

```
Web App → Location Service (:8001) → Redis GEO
Web App → Event Service (:8002) → Redis GEOSEARCH → Notification Service (:8003) → Redis Pub/Sub → WebSocket → Web App
```

Three independent FastAPI services share `backend/shared/` (schemas, config, redis_client, cors). Each has its own Dockerfile. Redis is the only stateful dependency.

## Code Conventions

- **PYTHONPATH=/app** inside Docker. All imports use `from backend.shared import ...`.
- Folder names use hyphens (`location-service`), NOT underscores. Cannot do normal Python import from these paths — use `importlib` if importing outside Docker.
- Pydantic v2 models live in `backend/shared/schemas.py`. Add new fields there.
- Redis client factory: `backend/shared/redis_client.py` → `create_redis()`.
- CORS config: `backend/shared/cors.py` → reads `CORS_ALLOW_ORIGINS` env var.
- Each service: `backend/<service>/app/main.py` is the FastAPI app entrypoint.
- Dockerfile copies `backend/shared` then `backend/<service>/app` into `/app/`.
- Frontend: React 18 + TypeScript + Vite + Leaflet. API base URLs via env vars.

## Env Vars

| Var | Default | Where |
|-----|---------|-------|
| `REDIS_URL` | `redis://localhost:6379/0` | shared/config.py |
| `USER_LOCATION_KEY` | `realtime_map_notice:user:locations` | shared/config.py |
| `USER_LAST_SEEN_PREFIX` | `realtime_map_notice:user:last_seen` | shared/config.py |
| `DEFAULT_ALERT_RADIUS_METERS` | `500` | shared/config.py |
| `CORS_ALLOW_ORIGINS` | `http://localhost:5173,http://localhost:3000` | shared/config.py |
| `NOTIFICATION_SERVICE_URL` | `http://localhost:8003` | event-service only |
| `EVENT_IDEMPOTENCY_TTL` | `300` | event-service only |

## Gotchas

- No `.env` file tracked — copy from `.env.example`.
- `web-app/.env` (copy from `.env.example`) for frontend service URLs.
- Cross-service integration tests require `docker compose up -d` first.
- `.dockerignore` is in place — `.git`, `__pycache__`, `tests/`, etc. excluded from build context.

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

Namespace: `realtime-map-notice`. All three services have HPA (1–5 replicas, CPU 60%). All have liveness + readiness probes on `/healthz`.

## Load Testing

```bash
python simulator/simulate_users.py --users 500 --target http://localhost:8001 --interval 1
# Advanced: --users 3000
```

Requires: `pip install -r simulator/requirements.txt`
