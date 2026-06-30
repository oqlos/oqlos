// Minimal WebSocket CQRS client compatible with maskservice core/ws-cqrs/ws-client.ts
// Messages are JSON with { message_type: 'command'|'query'|'event'|'response', data: {...} }.

const RECONNECT_DELAY_MS = 1000;
const RECONNECT_MAX_ATTEMPTS = 6;
const REQUEST_TIMEOUT_MS = 30_000;

function defaultUrl() {
  const fromEnv = import.meta.env.VITE_WS_URL;
  if (fromEnv) return fromEnv;
  const loc = window.location;
  const proto = loc.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${loc.host}/ws`;
}

export class WsCqrsClient extends EventTarget {
  constructor(url = defaultUrl()) {
    super();
    this.url = url;
    this.ws = null;
    this.pending = new Map();
    this.reconnectAttempts = 0;
    this.connectPromise = null;
    this.subs = new Map(); // eventType -> Set<handler>
    this._connected = false;
  }

  get connected() {
    return this._connected && this.ws?.readyState === WebSocket.OPEN;
  }

  connect() {
    if (this.connected) return Promise.resolve();
    if (this.connectPromise) return this.connectPromise;
    this.connectPromise = new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url);
      } catch (err) {
        this.connectPromise = null;
        reject(err);
        return;
      }
      this.ws.onopen = () => {
        this._connected = true;
        this.reconnectAttempts = 0;
        this.connectPromise = null;
        this.dispatchEvent(new Event("open"));
        resolve();
      };
      this.ws.onclose = () => {
        this._connected = false;
        this.connectPromise = null;
        this.dispatchEvent(new Event("close"));
        this._scheduleReconnect();
      };
      this.ws.onerror = (ev) => {
        this.dispatchEvent(new CustomEvent("error", { detail: ev }));
        if (!this._connected) {
          this.connectPromise = null;
          reject(new Error("WebSocket connection failed"));
        }
      };
      this.ws.onmessage = (ev) => this._handleMessage(ev.data);
    });
    return this.connectPromise;
  }

  disconnect() {
    if (this.ws) { this.ws.close(); this.ws = null; }
    this._connected = false;
  }

  async command(type, payload = {}) {
    return this._request("command", type, payload);
  }

  async query(type, payload = {}) {
    return this._request("query", type, payload);
  }

  subscribe(eventType, handler) {
    if (!this.subs.has(eventType)) this.subs.set(eventType, new Set());
    this.subs.get(eventType).add(handler);
    return () => this.subs.get(eventType)?.delete(handler);
  }

  async _request(kind, type, payload) {
    await this.connect();
    const id = `${kind === "command" ? "cmd" : "qry"}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`${kind} timeout: ${type}`));
      }, REQUEST_TIMEOUT_MS);
      this.pending.set(id, { resolve, reject, timeout });
      const key = kind === "command" ? "command_id" : "query_id";
      this.ws.send(JSON.stringify({
        message_type: kind,
        data: { type, [key]: id, ...payload },
      }));
    });
  }

  _handleMessage(raw) {
    let msg;
    try { msg = JSON.parse(raw); } catch { return; }
    if (msg.message_type === "response") {
      const response = msg.data || {};
      const pending = this.pending.get(response.correlation_id);
      if (pending) {
        clearTimeout(pending.timeout);
        this.pending.delete(response.correlation_id);
        if (response.success) pending.resolve(response.data);
        else pending.reject(new Error(response.error || "Command failed"));
      }
    } else if (msg.message_type === "event") {
      const evt = msg.data || {};
      const handlers = this.subs.get(evt.event_type);
      handlers?.forEach((h) => { try { h(evt); } catch {/* no-op */} });
      this.subs.get("*")?.forEach((h) => { try { h(evt); } catch {/* no-op */} });
      this.dispatchEvent(new CustomEvent("event", { detail: evt }));
    }
  }

  _scheduleReconnect() {
    if (this.reconnectAttempts >= RECONNECT_MAX_ATTEMPTS) return;
    const delay = RECONNECT_DELAY_MS * Math.pow(2, this.reconnectAttempts++);
    setTimeout(() => {
      this.connect().catch(() => {/* retry again from onclose */});
    }, delay);
  }
}

let singleton = null;
export function getWsClient() {
  if (!singleton) singleton = new WsCqrsClient();
  return singleton;
}
