import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { updateLocation } from '../locationApi';

describe('locationApi', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('calls POST /locations with correct payload', async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      json: () => Promise.resolve({ status: 'accepted', user_id: 'u-test' }),
    };
    vi.mocked(fetch).mockResolvedValueOnce(mockResponse as Response);

    const result = await updateLocation({
      user_id: 'u-test',
      latitude: 25.0173,
      longitude: 121.5397,
    });

    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8001/locations',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'u-test',
          latitude: 25.0173,
          longitude: 121.5397,
        }),
      }),
    );
    expect(result).toEqual({ status: 'accepted', user_id: 'u-test' });
  });

  it('throws on non-ok response', async () => {
    const mockResponse = {
      ok: false,
      status: 500,
      text: () => Promise.resolve('Internal error'),
    };
    vi.mocked(fetch).mockResolvedValueOnce(mockResponse as Response);

    await expect(
      updateLocation({ user_id: 'u-test', latitude: 25.0, longitude: 121.0 }),
    ).rejects.toThrow('Location update failed');
  });
});

import { createEvent } from '../eventApi';

describe('eventApi', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('calls POST /events with correct payload', async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve({
          event_id: 'evt-1',
          nearby_user_count: 5,
          delivered_count: 5,
          delivered_to: ['u-1'],
        }),
    };
    vi.mocked(fetch).mockResolvedValueOnce(mockResponse as Response);

    const result = await createEvent({
      title: 'Test',
      message: 'Hello',
      latitude: 25.0173,
      longitude: 121.5397,
      severity: 'info',
      radius_meters: 500,
    });

    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8002/events',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    expect(result.event_id).toBe('evt-1');
    expect(result.delivered_count).toBe(5);
  });
});
