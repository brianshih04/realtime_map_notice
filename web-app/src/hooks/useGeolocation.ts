import { useState, useEffect, useCallback } from 'react';

export interface GeolocationState {
  latitude: number | null;
  longitude: number | null;
  accuracy: number | null;
  error: string | null;
  loading: boolean;
}

const NTU_CENTER = { latitude: 25.0173, longitude: 121.5397 };

/**
 * Hook that wraps the browser Geolocation API.
 *
 * - Watches position continuously (high accuracy).
 * - Falls back to NTU campus center on error or denial.
 * - Exposes accuracy for UI hints when accuracy is poor (>100m).
 */
export function useGeolocation(watch = true): GeolocationState {
  const [state, setState] = useState<GeolocationState>({
    latitude: null,
    longitude: null,
    accuracy: null,
    error: null,
    loading: true,
  });

  const fallback = useCallback(() => {
    setState({
      latitude: NTU_CENTER.latitude,
      longitude: NTU_CENTER.longitude,
      accuracy: null,
      error: 'Location unavailable — using default campus center.',
      loading: false,
    });
  }, []);

  useEffect(() => {
    if (!watch) {
      // Single-shot position
      if ('geolocation' in navigator) {
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            setState({
              latitude: pos.coords.latitude,
              longitude: pos.coords.longitude,
              accuracy: pos.coords.accuracy,
              error: null,
              loading: false,
            });
          },
          (err) => {
            console.warn('Geolocation error:', err.message);
            fallback();
          },
          { enableHighAccuracy: true, timeout: 10_000, maximumAge: 0 },
        );
      } else {
        fallback();
      }
      return;
    }

    if (!('geolocation' in navigator)) {
      fallback();
      return;
    }

    const watchId = navigator.geolocation.watchPosition(
      (pos) => {
        setState({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
          error: null,
          loading: false,
        });
      },
      (err) => {
        console.warn('Geolocation error:', err.message);
        fallback();
      },
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 1_000 },
    );

    return () => {
      navigator.geolocation.clearWatch(watchId);
    };
  }, [watch, fallback]);

  return state;
}
