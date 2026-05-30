import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock the websocket module
vi.mock('../../services/websocket', () => ({
  createNotificationSocket: vi.fn(() => ({
    connect: vi.fn(),
    disconnect: vi.fn(),
    onNotification: null,
    status: 'connected',
  })),
}));

import { renderHook, act } from '@testing-library/react';
import { useNotificationSocket } from '../../hooks/useNotificationSocket';
import { createNotificationSocket } from '../../services/websocket';

describe('useNotificationSocket', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('does not connect when userId is null', () => {
    renderHook(() => useNotificationSocket(null));
    expect(createNotificationSocket).not.toHaveBeenCalled();
  });

  it('connects when userId is provided', () => {
    const mockSocket = {
      connect: vi.fn(),
      disconnect: vi.fn(),
      onNotification: null as ((n: unknown) => void) | null,
      status: 'connected' as const,
    };
    vi.mocked(createNotificationSocket).mockReturnValue(mockSocket);

    const { unmount } = renderHook(() => useNotificationSocket('test-user'));

    expect(createNotificationSocket).toHaveBeenCalledWith('test-user');
    expect(mockSocket.connect).toHaveBeenCalled();

    // Status should update via interval
    act(() => {
      vi.advanceTimersByTime(600);
    });

    unmount();
    expect(mockSocket.disconnect).toHaveBeenCalled();
  });
});
