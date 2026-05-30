import { useCallback, useEffect, useRef, useState } from 'react';
import MapView, { type MapEvent } from './components/MapView';
import EventForm from './components/EventForm';
import EventList from './components/EventList';
import NotificationBanner from './components/NotificationBanner';
import { useGeolocation } from './hooks/useGeolocation';
import { useNotificationSocket } from './hooks/useNotificationSocket';
import { updateLocation } from './services/locationApi';
import type { EventCreateResponse } from './types/api';

const USER_ID_KEY = 'realtime_map_notice_user_id';
const UPDATE_INTERVAL_MS = 1_000; // Demo: 1s; production: 2–3s

function getUserId(): string {
  let id = localStorage.getItem(USER_ID_KEY);
  if (!id) {
    id = `u-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    localStorage.setItem(USER_ID_KEY, id);
  }
  return id;
}

export default function App() {
  const userId = useRef(getUserId()).current;

  const geo = useGeolocation(true);
  const { status: wsStatus, lastNotification, clearNotification } =
    useNotificationSocket(userId);

  const [events, setEvents] = useState<MapEvent[]>([]);
  const [flyToCoord, setFlyToCoord] = useState<{
    lat: number;
    lng: number;
  } | null>(null);
  const [showEventList, setShowEventList] = useState(false);

  // Periodic location upload
  useEffect(() => {
    if (geo.latitude == null || geo.longitude == null) return;

    const interval = setInterval(() => {
      updateLocation({
        user_id: userId,
        latitude: geo.latitude!,
        longitude: geo.longitude!,
      }).catch((err) => {
        console.warn('Location update failed:', err.message);
      });
    }, UPDATE_INTERVAL_MS);

    // Upload immediately on first fix
    updateLocation({
      user_id: userId,
      latitude: geo.latitude!,
      longitude: geo.longitude!,
    }).catch((err) => {
      console.warn('Initial location update failed:', err.message);
    });

    return () => clearInterval(interval);
  }, [geo.latitude, geo.longitude, userId]);

  // Add incoming notifications to the event list
  useEffect(() => {
    if (lastNotification) {
      const mapEvent: MapEvent = {
        event_id: lastNotification.event_id,
        title: lastNotification.title,
        latitude: lastNotification.latitude,
        longitude: lastNotification.longitude,
        severity: lastNotification.severity,
        distance_meters: lastNotification.distance_meters,
      };
      setEvents((prev) => {
        // Deduplicate by event_id
        if (prev.some((e) => e.event_id === mapEvent.event_id)) return prev;
        return [...prev.slice(-49), mapEvent]; // keep last 50
      });
    }
  }, [lastNotification]);

  const handleEventCreated = useCallback(
    (response: EventCreateResponse) => {
      // Add self-posted event to map
      if (geo.latitude != null && geo.longitude != null) {
        const mapEvent: MapEvent = {
          event_id: response.event_id,
          title: `📢 You posted an event`,
          latitude: geo.latitude,
          longitude: geo.longitude,
          severity: 'info',
          distance_meters: 0,
        };
        setEvents((prev) => [...prev.slice(-49), mapEvent]);
      }
    },
    [geo.latitude, geo.longitude],
  );

  const handleViewLocation = useCallback((lat: number, lng: number) => {
    setFlyToCoord({ lat, lng });
  }, []);

  const handleSelectEvent = useCallback((evt: MapEvent) => {
    setFlyToCoord({ lat: evt.latitude, lng: evt.longitude });
    setShowEventList(false);
  }, []);

  return (
    <div className="app">
      {/* Connection status indicator */}
      <div className={`connection-status ${wsStatus}`}>
        {wsStatus === 'connected' && '🟢 Live'}
        {wsStatus === 'connecting' && '🟡 Connecting...'}
        {wsStatus === 'reconnecting' && '🟠 Reconnecting...'}
        {wsStatus === 'disconnected' && '🔴 Offline'}
      </div>

      {/* Location accuracy warning */}
      {geo.accuracy != null && geo.accuracy > 100 && (
        <div className="accuracy-warning">
          ⚠️ GPS accuracy is low ({Math.round(geo.accuracy)}m). Location may be inaccurate.
        </div>
      )}

      {/* Notification banner */}
      <NotificationBanner
        notification={lastNotification}
        onClear={clearNotification}
        onViewLocation={handleViewLocation}
      />

      {/* Map — always full screen */}
      <MapView
        userLat={geo.latitude}
        userLng={geo.longitude}
        events={events}
        flyToCoord={flyToCoord}
        onFlyComplete={() => setFlyToCoord(null)}
      />

      {/* Top bar */}
      <div className="top-bar">
        <h1 className="top-bar-title">NTU Campus Alerts</h1>
        <button
          className="top-bar-btn"
          onClick={() => setShowEventList(!showEventList)}
        >
          {showEventList ? '✕ Close' : `📋 Events (${events.length})`}
        </button>
      </div>

      {/* Slide-out event list */}
      {showEventList && (
        <div className="event-list-panel">
          <EventList events={events} onSelectEvent={handleSelectEvent} />
        </div>
      )}

      {/* Floating event form */}
      <EventForm
        latitude={geo.latitude}
        longitude={geo.longitude}
        onEventCreated={handleEventCreated}
      />

      {/* Geolocation error fallback */}
      {geo.error && (
        <div className="location-error-banner">
          {geo.error}
        </div>
      )}
    </div>
  );
}
