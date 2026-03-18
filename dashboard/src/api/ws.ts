/**
 * AECO WebSocket client for real-time event streaming.
 *
 * Connects to /api/ws and dispatches events to registered listeners.
 * Auto-reconnects with exponential backoff on disconnect.
 */

type EventHandler = (event: AECOEvent) => void;

export interface AECOEvent {
  type: string;
  timestamp: string;
  data: Record<string, unknown>;
}

const WS_BASE = import.meta.env.VITE_WS_URL || `ws://${window.location.host}`;
const MAX_RECONNECT_DELAY = 30_000;

class AECOWebSocket {
  private ws: WebSocket | null = null;
  private listeners = new Map<string, Set<EventHandler>>();
  private reconnectDelay = 1000;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = true;

  /** Connect to the AECO WebSocket endpoint. */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    this.shouldReconnect = true;

    try {
      this.ws = new WebSocket(`${WS_BASE}/api/ws`);
    } catch {
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      console.log('[AECO WS] connected');
      this.reconnectDelay = 1000;
    };

    this.ws.onmessage = (msg) => {
      try {
        const event: AECOEvent = JSON.parse(msg.data);
        this.dispatch(event);
      } catch {
        // Ignore malformed messages
      }
    };

    this.ws.onclose = () => {
      console.log('[AECO WS] disconnected');
      if (this.shouldReconnect) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  /** Disconnect and stop reconnecting. */
  disconnect(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
  }

  /**
   * Subscribe to events matching a type pattern.
   * Use "*" to match all events, or "initiative.*" for prefix matching.
   * Returns an unsubscribe function.
   */
  on(pattern: string, handler: EventHandler): () => void {
    if (!this.listeners.has(pattern)) {
      this.listeners.set(pattern, new Set());
    }
    this.listeners.get(pattern)!.add(handler);

    return () => {
      this.listeners.get(pattern)?.delete(handler);
      if (this.listeners.get(pattern)?.size === 0) {
        this.listeners.delete(pattern);
      }
    };
  }

  /** Send a filter subscription to the server. */
  subscribe(patterns: string[]): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ subscribe: patterns }));
    }
  }

  private dispatch(event: AECOEvent): void {
    for (const [pattern, handlers] of this.listeners) {
      if (this.matches(event.type, pattern)) {
        for (const handler of handlers) {
          try {
            handler(event);
          } catch {
            // Don't let one handler break others
          }
        }
      }
    }
  }

  private matches(eventType: string, pattern: string): boolean {
    if (pattern === '*') return true;
    if (pattern.endsWith('.*')) {
      return eventType.startsWith(pattern.slice(0, -2) + '.');
    }
    return eventType === pattern;
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    console.log(`[AECO WS] reconnecting in ${this.reconnectDelay}ms`);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, MAX_RECONNECT_DELAY);
      this.connect();
    }, this.reconnectDelay);
  }
}

/** Singleton WebSocket client */
export const aecoWs = new AECOWebSocket();
