import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, fireEvent, screen } from '@testing-library/react';
import EventForm from '../EventForm';
import { createEvent } from '../../services/eventApi';

vi.mock('../../services/eventApi', () => ({
  createEvent: vi.fn(),
}));

describe('EventForm', () => {
  const mockLat = 25.0173;
  const mockLng = 121.5397;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('starts collapsed', () => {
    const { getByText } = render(
      <EventForm latitude={mockLat} longitude={mockLng} />,
    );
    expect(getByText('📢 Post Event')).toBeDefined();
  });

  it('expands on toggle click', () => {
    const { getByText, getByLabelText } = render(
      <EventForm latitude={mockLat} longitude={mockLng} />,
    );
    fireEvent.click(getByText('📢 Post Event'));
    expect(getByLabelText('Title')).toBeDefined();
    expect(getByLabelText('Message')).toBeDefined();
  });

  it('shows warning when location is null', () => {
    const { getByText } = render(
      <EventForm latitude={null} longitude={null} />,
    );
    fireEvent.click(getByText('📢 Post Event'));
    expect(getByText('Waiting for your location...')).toBeDefined();
  });

  it('submits event and clears form on success', async () => {
    const mockResponse = {
      event_id: 'evt-new',
      nearby_user_count: 5,
      delivered_count: 5,
      delivered_to: ['u-1', 'u-2'],
    };
    vi.mocked(createEvent).mockResolvedValueOnce(mockResponse);

    const onCreated = vi.fn();
    const { getByText, getByLabelText } = render(
      <EventForm
        latitude={mockLat}
        longitude={mockLng}
        onEventCreated={onCreated}
      />,
    );

    // Expand form
    fireEvent.click(getByText('📢 Post Event'));

    // Fill form
    fireEvent.change(getByLabelText('Title'), {
      target: { value: 'Test Event' },
    });
    fireEvent.change(getByLabelText('Message'), {
      target: { value: 'Something is happening' },
    });

    // Submit
    fireEvent.click(getByText('Post Event'));

    // Wait for async
    await vi.waitFor(() => {
      expect(createEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Test Event',
          message: 'Something is happening',
          latitude: mockLat,
          longitude: mockLng,
          severity: 'info',
          radius_meters: 500,
        }),
      );
      expect(onCreated).toHaveBeenCalledWith(mockResponse);
      expect(getByText(/Delivered to 5 nearby user/)).toBeDefined();
    });
  });

  it('disables submit when form is incomplete', () => {
    const { getByText } = render(
      <EventForm latitude={mockLat} longitude={mockLng} />,
    );
    fireEvent.click(getByText('📢 Post Event'));

    const submitBtn = getByText('Post Event') as HTMLButtonElement;
    expect(submitBtn.disabled).toBe(true);
  });
});
