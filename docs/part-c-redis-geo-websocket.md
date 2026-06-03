# Part C: Redis GEO + WebSocket Architecture

## 1. Role

Part C owns realtime location and nearby notification delivery.

In one sentence:

> Part C records where each user currently is, finds users within a target radius, and sends realtime event notifications to nearby online users.

## 2. Responsibilities

Part C is responsible for:

1. Receiving user location updates.
2. Storing current user locations in Redis GEO.
3. Querying users near an event coordinate.
4. Maintaining WebSocket connections.
5. Delivering event notifications to online nearby users.

Part C is not responsible for:

1. User registration or login.
2. Full event CRUD.
3. Long-term event storage.
4. Frontend map UI.
5. Kubernetes autoscaling and load test operation.

## 3. Current Repo Mapping

The current repo splits Part C into two backend services:

```text
backend/location-service
  Receives GPS updates and stores current locations in Redis GEO.

backend/notification-service
  Maintains WebSocket connections and publishes user notifications.
```

The event service connects the two:

```text
backend/event-service
  Creates an event, queries Redis GEO for nearby users, and calls notification-service.
```

## 4. Data Flow

### User Updates Location

```text
Frontend
  -> POST /locations
  -> location-service
  -> Redis GEO
```

Redis key:

```text
realtime_map_notice:user:locations
```

Redis operation:

```text
GEOADD realtime_map_notice:user:locations <longitude> <latitude> <user_id>
```

### Frontend Opens WebSocket

```text
Frontend
  -> WS /ws/{user_id}
  -> notification-service
```

The notification service subscribes to the user-specific Redis Pub/Sub channel:

```text
realtime_map_notice:user:{user_id}:notifications
```

### User Creates Event

```text
Frontend
  -> POST /events
  -> event-service
  -> Redis GEO search
  -> notification-service
  -> WebSocket client
```

Redis operation:

```text
GEOSEARCH realtime_map_notice:user:locations
  FROMLONLAT <longitude> <latitude>
  BYRADIUS <radius_meters> m
```

## 5. APIs Owned by Part C

### Location Service

Health check:

```http
GET /healthz
```

Update user location:

```http
POST /locations
```

Request:

```json
{
  "user_id": "alice",
  "latitude": 25.0330,
  "longitude": 121.5654
}
```

Query nearby users:

```http
GET /locations/nearby?latitude=25.0330&longitude=121.5654&radius_meters=500
```

Response:

```json
{
  "users": ["alice", "bob"]
}
```

### Notification Service

Health check:

```http
GET /healthz
```

Open realtime connection:

```http
WS /ws/{user_id}
```

Notify one user:

```http
POST /notify/{user_id}
```

Request:

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

## 6. First Milestone

Part C's first milestone should prove three things:

1. A user location can be updated into Redis GEO.
2. Nearby users can be queried within 500 meters.
3. A nearby online user can receive a WebSocket notification.

## 7. Local Demo Steps

Start services:

```powershell
docker compose up --build
```

Open API docs:

```text
http://localhost:8001/docs  location-service
http://localhost:8002/docs  event-service
http://localhost:8003/docs  notification-service
```

Suggested manual test:

1. Open a WebSocket client to `ws://localhost:8003/ws/alice`.
2. Call `POST http://localhost:8001/locations` for `alice` near the event coordinate.
3. Call `POST http://localhost:8001/locations` for `bob` farther away.
4. Call `POST http://localhost:8002/events`.
5. Confirm only nearby connected users receive the notification.

## 8. What to Build Next

Recommended next steps for Part C:

1. Add a simple WebSocket test client for local demos.
2. Add heartbeat or ping/pong handling so stale connections are cleaned up.
3. Return distance from nearby-user queries for easier debugging.
4. Add tests for Redis GEO queries with fake users around a campus coordinate.
5. Document the exact demo coordinates used by the team.

## 9. Important Notes

Redis GEO should store only current position lookup data, not full user profiles or permanent event history.

The notification service should focus on online delivery. If a user is offline, the current MVP can skip delivery instead of storing unread notifications.

For the final K8s demo, Part C should be tested locally with Docker Compose first. Kubernetes should be treated as the deployment layer, not the first place to debug application logic.
