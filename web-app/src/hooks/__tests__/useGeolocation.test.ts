import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useGeolocation } from '../../hooks/useGeolocation';

const mockGeolocation = {
  watchPosition: vi.fn(),
  clearWatch: vi.fn(),
  getCurrentPosition: vi.fn(),
};

describe('useGeolocation', () => {
  beforeEach(() => {
    (globalThis as Record<string, unknown>).navigator = {
      geolocation: mockGeolocation,
    };
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('starts with loading true and null coordinates', () => {
    mockGeolocation.watchPosition.mockImplementation(() => 1);

    const { result } = renderHook(() => useGeolocation(true));

    expect(result.current.loading).toBe(true);
    expect(result.current.latitude).toBeNull();
    expect(result.current.longitude).toBeNull();
  });

  it('falls back to NTU center when geolocation unavailable', () => {
    // Remove geolocation
    (globalThis as Record<string, unknown>).navigator = {};

    const { result } = renderHook(() => useGeolocation(true));

    expect(result.current.latitude).toBe(25.0173);
    expect(result.current.longitude).toBe(121.5397);
    expect(result.current.error).toBeTruthy();
    expect(result.current.loading).toBe(false);
  });
});
