import { useEffect, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
// Fix default marker icon issue with webpack/vite
import iconUrl from 'leaflet/dist/images/marker-icon.png';
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import shadowUrl from 'leaflet/dist/images/marker-shadow.png';

delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;
L.Icon.Default.mergeOptions({ iconUrl, iconRetinaUrl, shadowUrl });

const USER_ICON = new L.DivIcon({
  className: 'user-marker',
  html: `<div style="
    width:16px;height:16px;border-radius:50%;
    background:#2563eb;border:3px solid white;
    box-shadow:0 0 8px rgba(37,99,235,0.6);
  "></div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

const INFO_ICON = new L.DivIcon({
  className: 'event-marker event-info',
  html: `<div style="
    width:20px;height:20px;border-radius:4px;
    background:#f59e0b;border:2px solid white;
    box-shadow:0 0 6px rgba(245,158,11,0.5);
    transform:rotate(45deg);
  "></div>`,
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

const URGENT_ICON = new L.DivIcon({
  className: 'event-marker event-urgent',
  html: `<div style="
    width:24px;height:24px;border-radius:4px;
    background:#ef4444;border:2px solid white;
    box-shadow:0 0 10px rgba(239,68,68,0.7);
    transform:rotate(45deg);
    animation:pulse 1s infinite;
  "></div>`,
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

const NTU_CENTER: [number, number] = [25.0173, 121.5397];

export interface MapEvent {
  event_id: string;
  title: string;
  latitude: number;
  longitude: number;
  severity: string;
  distance_meters: number | null;
}

interface MapViewProps {
  userLat: number | null;
  userLng: number | null;
  events: MapEvent[];
  flyToCoord?: { lat: number; lng: number } | null;
  onFlyComplete?: () => void;
}

/** Sub-component that handles map.flyTo via useMap() hook. */
function MapController({
  flyToCoord,
  onFlyComplete,
}: {
  flyToCoord?: { lat: number; lng: number } | null;
  onFlyComplete?: () => void;
}) {
  const map = useMap();
  const hasFlown = useRef(false);

  useEffect(() => {
    if (flyToCoord && !hasFlown.current) {
      hasFlown.current = true;
      map.flyTo([flyToCoord.lat, flyToCoord.lng], 17, { duration: 1.5 });
      setTimeout(() => {
        hasFlown.current = false;
        onFlyComplete?.();
      }, 1600);
    }
  }, [flyToCoord, map, onFlyComplete]);

  return null;
}

export default function MapView({ userLat, userLng, events, flyToCoord, onFlyComplete }: MapViewProps) {
  const center: [number, number] = useMemo(() => {
    if (userLat != null && userLng != null) return [userLat, userLng];
    return NTU_CENTER;
  }, [userLat, userLng]);

  const showUser = userLat != null && userLng != null;

  return (
    <MapContainer
      center={center}
      zoom={16}
      style={{ width: '100%', height: '100%' }}
      zoomControl={false}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      <MapController flyToCoord={flyToCoord} onFlyComplete={onFlyComplete} />

      {showUser && (
        <Marker position={[userLat!, userLng!]} icon={USER_ICON}>
          <Popup>You are here</Popup>
        </Marker>
      )}

      {events.map((evt) => (
        <Marker
          key={evt.event_id}
          position={[evt.latitude, evt.longitude]}
          icon={evt.severity === 'urgent' ? URGENT_ICON : INFO_ICON}
        >
          <Popup>
            <strong>{evt.title}</strong>
            {evt.distance_meters != null && (
              <span style={{ marginLeft: 8, color: '#6b7280', fontSize: '0.85em' }}>
                {Math.round(evt.distance_meters)}m away
              </span>
            )}
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
