/** Location payload sent to the backend */
export interface LocationUpdate {
  user_id: string;
  latitude: number;
  longitude: number;
}

/** Event creation payload */
export interface EventCreate {
  title: string;
  message: string;
  latitude: number;
  longitude: number;
  severity: 'info' | 'urgent';
  radius_meters: number;
}

/** Event notification received via WebSocket */
export interface EventNotification {
  event_id: string;
  title: string;
  message: string;
  latitude: number;
  longitude: number;
  severity: string;
  distance_meters: number | null;
}

/** Response from POST /events */
export interface EventCreateResponse {
  event_id: string;
  nearby_user_count: number;
  delivered_count: number;
  delivered_to: string[];
}

/** Response from POST /locations */
export interface LocationResponse {
  status: string;
  user_id: string;
}

/** Response from GET /locations/nearby */
export interface NearbyUsersResponse {
  users: string[];
}
