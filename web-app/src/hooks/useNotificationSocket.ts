import { useEffect, useRef, useCallback, useState } from 'react';
import {
  createNotificationSocket,
  type ConnectionStatus,
} from '../services/websocket';
import type { EventNotification } from '../types/api';

interface UseNotificationSocketReturn {
  status: ConnectionStatus;
  lastNotification: EventNotification | null;
  clearNotification: () => void;
}

/**
 * Hook that manages a WebSocket connection to the notification service.
 *
 * - Connects on mount, disconnects on unmount.
 * - Auto-reconnects on disconnect with exponential backoff.
 * - Exposes connection status and the most recent notification.
 */
export function useNotificationSocket(userId: string | null): UseNotificationSocketReturn {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [lastNotification, setLastNotification] = useState<EventNotification | null>(null);
  const socketRef = useRef<ReturnType<typeof createNotificationSocket> | null>(null);
  const statusTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearNotification = useCallback(() => {
    setLastNotification(null);
  }, []);

  useEffect(() => {
    if (!userId) return;

    const socket = createNotificationSocket(userId);
    socketRef.current = socket;

    socket.onNotification = (notification: EventNotification) => {
      setLastNotification(notification);
    };

    socket.connect();

    // Poll status periodically (WebSocket doesn't expose real-time status easily)
    statusTimerRef.current = setInterval(() => {
      setStatus(socket.status);
    }, 500);

    return () => {
      if (statusTimerRef.current) {
        clearInterval(statusTimerRef.current);
      }
      socket.disconnect();
    };
  }, [userId]);

  return { status, lastNotification, clearNotification };
}
