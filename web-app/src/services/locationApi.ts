import type { LocationUpdate, LocationResponse } from '../types/api';

const BASE_URL = import.meta.env.VITE_LOCATION_SERVICE_URL || 'http://localhost:8001';

export async function updateLocation(payload: LocationUpdate): Promise<LocationResponse> {
  const res = await fetch(`${BASE_URL}/locations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Location update failed (${res.status}): ${text}`);
  }
  return res.json();
}
