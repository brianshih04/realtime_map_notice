import { useEffect, useState } from 'react';
import type { EventNotification } from '../types/api';

interface NotificationBannerProps {
  notification: EventNotification | null;
  onClear: () => void;
  onViewLocation?: (lat: number, lng: number) => void;
}

export default function NotificationBanner({
  notification,
  onClear,
  onViewLocation,
}: NotificationBannerProps) {
  const [visible, setVisible] = useState(false);
  const [dismissing, setDismissing] = useState(false);

  useEffect(() => {
    if (notification) {
      setVisible(true);
      setDismissing(false);
      // Auto-dismiss after 10 seconds if not urgent
      if (notification.severity !== 'urgent') {
        const timer = setTimeout(() => handleDismiss(), 10_000);
        return () => clearTimeout(timer);
      }
    } else {
      setVisible(false);
    }
  }, [notification]);

  function handleDismiss() {
    setDismissing(true);
    setTimeout(() => {
      setVisible(false);
      onClear();
    }, 300);
  }

  if (!notification || !visible) return null;

  const isUrgent = notification.severity === 'urgent';

  return (
    <div
      className={`notification-banner ${isUrgent ? 'urgent' : 'info'} ${dismissing ? 'dismissing' : ''}`}
      role="alert"
      aria-live="assertive"
    >
      <div className="notification-banner-content">
        <span className="notification-banner-icon">
          {isUrgent ? '🚨' : 'ℹ️'}
        </span>
        <div className="notification-banner-text">
          <strong>{notification.title}</strong>
          {notification.distance_meters != null && (
            <span className="notification-banner-distance">
              {Math.round(notification.distance_meters)}m away
            </span>
          )}
          <p>{notification.message}</p>
        </div>
      </div>
      <div className="notification-banner-actions">
        {onViewLocation && (
          <button
            className="notification-banner-btn view"
            onClick={() =>
              onViewLocation(notification.latitude, notification.longitude)
            }
          >
            View Location
          </button>
        )}
        <button
          className="notification-banner-btn dismiss"
          onClick={handleDismiss}
          aria-label="Dismiss notification"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
