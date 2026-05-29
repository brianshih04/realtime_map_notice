import { useEffect, useRef } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  useMap,
  useMapEvents,
} from "react-leaflet";
import L from "leaflet";
import type { MapEvent } from "../types/api";
import "leaflet/dist/leaflet.css";

// Fix default marker icon paths (Leaflet + bundler issue)
import iconUrl from "leaflet/dist/images/marker-icon.png";
import iconRetinaUrl from "leaflet/dist/images/marker-icon-2x.png";
import shadowUrl from "leaflet/dist/images/marker-shadow.png";

const defaultIconPrototype = L.Icon.Default.prototype as L.Icon.Default & {
  _getIconUrl?: unknown;
};
delete defaultIconPrototype._getIconUrl;
L.Icon.Default.mergeOptions({ iconUrl, iconRetinaUrl, shadowUrl });

const urgentIcon = new L.Icon({
  iconUrl,
  iconRetinaUrl,
  shadowUrl,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  className: "urgent-marker",
});

const infoIcon = new L.Icon({
  iconUrl,
  iconRetinaUrl,
  shadowUrl,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  className: "info-marker",
});

interface MapViewProps {
  userLocation: { latitude: number; longitude: number } | null;
  events: MapEvent[];
  onMapClick: (lat: number, lng: number) => void;
  onEventClick: (event: MapEvent) => void;
  pendingLocation: { latitude: number; longitude: number } | null;
  focusLocation: { latitude: number; longitude: number } | null;
  onRecenter?: () => void;
}

function MapController({
  userLocation,
  focusLocation,
}: {
  userLocation: { latitude: number; longitude: number } | null;
  focusLocation: { latitude: number; longitude: number } | null;
}) {
  const map = useMap();
  const hasCentered = useRef(false);

  // focusLocation：每次都跟隨（點擊事件通知時跳轉）
  useEffect(() => {
    if (focusLocation) {
      map.setView([focusLocation.latitude, focusLocation.longitude], 17);
    }
  }, [focusLocation, map]);

  // userLocation：只在首次取得時 recenter 一次
  useEffect(() => {
    if (userLocation && !hasCentered.current) {
      hasCentered.current = true;
      map.setView([userLocation.latitude, userLocation.longitude], map.getZoom());
    }
  }, [userLocation, map]);

  return null;
}

function ClickHandler({
  onClick,
}: {
  onClick: (lat: number, lng: number) => void;
}) {
  useMapEvents({
    click(e) {
      onClick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

export default function MapView({
  userLocation,
  events,
  onMapClick,
  onEventClick,
  pendingLocation,
  focusLocation,
}: MapViewProps) {
  const defaultCenter: [number, number] = userLocation
    ? [userLocation.latitude, userLocation.longitude]
    : [25.0173, 121.5397];

  const mapRef = useRef<L.Map | null>(null);

  return (
    <MapContainer
      ref={mapRef}
      center={defaultCenter}
      zoom={16}
      zoomControl={false}
      style={{ width: "100%", height: "100%" }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ZoomControl position="bottomleft" />
      <MapController userLocation={userLocation} focusLocation={focusLocation} />
      <ClickHandler onClick={onMapClick} />

      {/* User location marker */}
      {userLocation && (
        <Marker position={[userLocation.latitude, userLocation.longitude]}>
          <Popup>你的位置</Popup>
        </Marker>
      )}

      {/* Pending event location marker */}
      {pendingLocation && (
        <Marker position={[pendingLocation.latitude, pendingLocation.longitude]} />
      )}

      {/* Event markers */}
      {events.map((event) => (
        <Marker
          key={event.id}
          position={[event.latitude, event.longitude]}
          icon={event.severity === "urgent" ? urgentIcon : infoIcon}
          eventHandlers={{
            click: () => onEventClick(event),
          }}
        >
          <Popup>
            <strong>{event.title}</strong>
            <p>{event.message}</p>
            {event.distance_meters != null && (
              <small>距離 {Math.round(event.distance_meters)} 公尺</small>
            )}
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}

function ZoomControl({ position }: { position: string }) {
  const map = useMap();

  useEffect(() => {
    const zoom = (L.control as unknown as { zoom: (opts: { position: string }) => L.Control.Zoom }).zoom({ position });
    zoom.addTo(map);
    return () => { zoom.remove(); };
  }, [map, position]);

  return null;
}
