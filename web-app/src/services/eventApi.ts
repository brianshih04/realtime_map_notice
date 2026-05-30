import type { EventCreate, EventCreateResponse } from '../types/api';

const BASE_URL = import.meta.env.VITE_EVENT_SERVICE_URL || 'http://localhost:8002';

export async function createEvent(payload: EventCreate): Promise<EventCreateResponse> {
  const res = await fetch(`${BASE_URL}/events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Event creation failed (${res.status}): ${text}`);
  }
  return res.json();
}
