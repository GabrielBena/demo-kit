// WebSocket client — sends actions, receives typed server messages, auto-reconnects.
// Pure transport; no model logic.

import type { BaseMsg, Handlers } from "./types.js";

export interface NetOptions<M extends BaseMsg> {
  /** Defaults to `ws(s)://<location.host>/ws` — the demo-kit server's endpoint. */
  url?: string;
  /** One optional callback per message `type` (fully typed via the union). */
  handlers: Handlers<M>;
  /** Connection up/down (fires on open/close — drive a status dot). */
  onStatus?: (up: boolean) => void;
  /** Message types with no handler land here; default warns on `error` frames. */
  onUnhandled?: (m: M) => void;
  /** Auto-reconnect delay after an unexpected close (ms). */
  reconnectMs?: number;
}

export class Net<M extends BaseMsg = BaseMsg> {
  private ws: WebSocket | null = null;
  private closed = false;

  constructor(private opts: NetOptions<M>) {}

  connect(): void {
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const url = this.opts.url ?? `${scheme}://${location.host}/ws`;
    const ws = new WebSocket(url);
    this.ws = ws;
    ws.onopen = () => this.opts.onStatus?.(true);
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data) as M;
      const h = this.opts.handlers[msg.type as M["type"]];
      if (h) h(msg as Extract<M, { type: M["type"] }>);
      else if (this.opts.onUnhandled) this.opts.onUnhandled(msg);
      else if (msg.type === "error") console.warn("[server]", (msg as BaseMsg & { msg?: string }).msg);
    };
    ws.onerror = () => ws.close();
    ws.onclose = () => {
      this.opts.onStatus?.(false);
      if (!this.closed) setTimeout(() => this.connect(), this.opts.reconnectMs ?? 1000);
    };
  }

  send(action: object): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(action));
  }

  close(): void {
    this.closed = true;
    this.ws?.close();
  }
}
