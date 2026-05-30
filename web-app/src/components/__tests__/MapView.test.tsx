import { describe, it, expect, vi } from 'vitest';

// Mock PNG imports that MapView uses for marker icons
vi.mock('leaflet/dist/images/marker-icon.png', () => ({ default: '' }));
vi.mock('leaflet/dist/images/marker-icon-2x.png', () => ({ default: '' }));
vi.mock('leaflet/dist/images/marker-shadow.png', () => ({ default: '' }));

// Mock leaflet BEFORE importing MapView
vi.mock('leaflet', () => ({
  default: {
    Icon: {
      Default: {
        prototype: {},
        mergeOptions: vi.fn(),
      },
    },
    DivIcon: vi.fn(() => ({})),
  },
}));

// Mock react-leaflet
vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="map-container">{children}</div>
  ),
  TileLayer: () => <div data-testid="tile-layer" />,
  Marker: ({ children, position }: { children?: React.ReactNode; position: [number, number] }) => (
    <div data-testid={`marker-${position[0]}-${position[1]}`}>{children}</div>
  ),
  Popup: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="popup">{children}</div>
  ),
  useMap: () => ({
    flyTo: vi.fn(),
  }),
}));

import { render } from '@testing-library/react';
import MapView, { type MapEvent } from '../MapView';

describe('MapView', () => {
  const mockEvents: MapEvent[] = [
    {
      event_id: 'evt-1',
      title: 'Test Event',
      latitude: 25.0178,
      longitude: 121.5402,
      severity: 'info',
      distance_meters: 100,
    },
    {
      event_id: 'evt-2',
      title: 'Urgent Event',
      latitude: 25.018,
      longitude: 121.54,
      severity: 'urgent',
      distance_meters: 50,
    },
  ];

  it('renders map container', () => {
    const { getByTestId } = render(
      <MapView userLat={null} userLng={null} events={[]} />,
    );
    expect(getByTestId('map-container')).toBeDefined();
  });

  it('shows user marker when location provided', () => {
    const { getByTestId } = render(
      <MapView userLat={25.0173} userLng={121.5397} events={[]} />,
    );
    expect(getByTestId('marker-25.0173-121.5397')).toBeDefined();
  });

  it('does not show user marker when location is null', () => {
    const { queryByTestId } = render(
      <MapView userLat={null} userLng={null} events={[]} />,
    );
    expect(queryByTestId('marker-25.0173-121.5397')).toBeNull();
  });

  it('shows event markers', () => {
    const { getByTestId } = render(
      <MapView userLat={25.0173} userLng={121.5397} events={mockEvents} />,
    );
    // User marker
    expect(getByTestId('marker-25.0173-121.5397')).toBeDefined();
    // Event markers (different coords from user)
    expect(getByTestId('marker-25.0178-121.5402')).toBeDefined();
    expect(getByTestId('marker-25.018-121.54')).toBeDefined();
  });
});
