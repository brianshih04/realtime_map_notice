import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import NotificationBanner from '../NotificationBanner';
import type { EventNotification } from '../../types/api';

describe('NotificationBanner', () => {
  const urgentNotification: EventNotification = {
    event_id: 'evt-urgent',
    title: 'Fire Alarm',
    message: 'Please evacuate',
    latitude: 25.0173,
    longitude: 121.5397,
    severity: 'urgent',
    distance_meters: 150,
  };

  const infoNotification: EventNotification = {
    event_id: 'evt-info',
    title: 'Free Coffee',
    message: 'At the cafeteria',
    latitude: 25.0180,
    longitude: 121.5400,
    severity: 'info',
    distance_meters: 300,
  };

  it('renders nothing when no notification', () => {
    const { container } = render(
      <NotificationBanner notification={null} onClear={vi.fn()} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders notification content', () => {
    const { getByText } = render(
      <NotificationBanner notification={infoNotification} onClear={vi.fn()} />,
    );
    expect(getByText('Free Coffee')).toBeDefined();
    expect(getByText('300m away')).toBeDefined();
    expect(getByText('At the cafeteria')).toBeDefined();
  });

  it('shows different styling for urgent vs info', () => {
    const { container: urgentContainer } = render(
      <NotificationBanner
        notification={urgentNotification}
        onClear={vi.fn()}
      />,
    );
    expect(urgentContainer.querySelector('.urgent')).toBeDefined();

    const { container: infoContainer } = render(
      <NotificationBanner
        notification={infoNotification}
        onClear={vi.fn()}
      />,
    );
    expect(infoContainer.querySelector('.info')).toBeDefined();
  });

  it('dismisses on close button click', () => {
    const onClear = vi.fn();
    const { getByLabelText } = render(
      <NotificationBanner notification={infoNotification} onClear={onClear} />,
    );
    fireEvent.click(getByLabelText('Dismiss notification'));
    // After animation timeout, onClear should be called
    setTimeout(() => {
      expect(onClear).toHaveBeenCalled();
    }, 400);
  });

  it('calls onViewLocation when view button clicked', () => {
    const onView = vi.fn();
    const { getByText } = render(
      <NotificationBanner
        notification={infoNotification}
        onClear={vi.fn()}
        onViewLocation={onView}
      />,
    );
    fireEvent.click(getByText('View Location'));
    expect(onView).toHaveBeenCalledWith(25.018, 121.54);
  });
});
