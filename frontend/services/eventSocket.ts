import { apiService } from './apiService';

export type BackendEvent =
  | { type: 'connection'; status: string; message: string; user_id?: string }
  | { type: 'job_update'; job: any; user_id?: string }
  | { type: string; [key: string]: any };

export const connectEventSocket = (
  userId: string,
  onEvent: (event: BackendEvent) => void,
  onError?: (error: Event) => void
) => {
  let ws: WebSocket | null = null;
  let reconnectTimer: number | null = null;
  let pingTimer: number | null = null;
  let disposed = false;
  let hasConnectedOnce = false;

  const clearTimers = () => {
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (pingTimer !== null) {
      window.clearInterval(pingTimer);
      pingTimer = null;
    }
  };

  const scheduleReconnect = () => {
    if (disposed || reconnectTimer !== null) {
      return;
    }
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, 3000);
  };

  const connect = () => {
    if (disposed) {
      return;
    }

    ws = new WebSocket(apiService.getEventsWebSocketUrl(userId));

    ws.onopen = () => {
      hasConnectedOnce = true;
      pingTimer = window.setInterval(() => {
        if (ws?.readyState === WebSocket.OPEN) {
          ws.send('ping');
        }
      }, 20000);
    };

    ws.onmessage = (event: MessageEvent<string>) => {
      try {
        const parsed = JSON.parse(event.data) as BackendEvent;
        onEvent(parsed);
      } catch (err) {
        console.error('Failed to parse backend event socket payload:', err);
      }
    };

    ws.onerror = (error) => {
      if (hasConnectedOnce && onError) {
        onError(error);
      }
    };

    ws.onclose = () => {
      if (pingTimer !== null) {
        window.clearInterval(pingTimer);
        pingTimer = null;
      }
      scheduleReconnect();
    };
  };

  connect();

  return () => {
    disposed = true;
    clearTimers();
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      ws.close();
    }
  };
};
