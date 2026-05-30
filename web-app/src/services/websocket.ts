import type { EventNotification } from '../types/api';

const WS_BASE = import.meta.env.VITE_NOTIFICATION_WS_URL || 'ws://localhost:8003';

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'reconnecting';

export interface NotificationSocket {
  connect: () => void;
  disconnect: () => void;
  onNotification: ((notification: EventNotification) => void) | null;
  status: ConnectionStatus;
}

/**
 * Create a WebSocket connection to the notification service.
 *
 * Auto-reconnects with exponential backoff (1s → 2s → 4s → ... max 30s).
 * On each successful connection the backoff resets.
 */
export function createNotificationSocket(
  userId: string,
): NotificationSocket {
  let ws: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let reconnectAttempts = 0;
  let _status: ConnectionStatus = 'disconnected';
  let _onNotification: ((n: EventNotification) => void) | null = null;

  const MAX_BACKOFF = 30_000;
  const BASE_BACKOFF = 1_000;

  function setStatus(s: ConnectionStatus) {
    _status = s;
  }

  function doConnect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    setStatus('connecting');
    const url = `${WS_BASE}/ws/${userId}`;
    ws = new WebSocket(url);

    ws.onopen = () => {
      setStatus('connected');
      reconnectAttempts = 0;
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data as string);
        // Ignore ping/heartbeat frames
        if (data.type === 'ping') return;
        // Assume anything else is an EventNotification
        if (_onNotification && data.event_id) {
          _onNotification(data as EventNotification);
        }
      } catch {
        // Ignore unparseable messages
      }
    };

    ws.onclose = () => {
      setStatus('disconnected');
      ws = null;
      scheduleReconnect();
    };

    ws.onerror = () => {
      // onclose will fire after onerror
    };
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    const delay = Math.min(BASE_BACKOFF * 2 ** reconnectAttempts, MAX_BACKOFF);
    reconnectAttempts += 1;
    setStatus('reconnecting');
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      doConnect();
    }, delay);
  }

  return {
    connect() {
      doConnect();
    },

    disconnect() {
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (ws) {
        ws.onclose = null; // prevent reconnect
        ws.close();
        ws = null;
      }
      setStatus('disconnected');
      reconnectAttempts = 0;
    },

    get status() {
      return _status;
    },

    set onNotification(cb: ((n: EventNotification) => void) | null) {
      _onNotification = cb;
    },
  };
}
