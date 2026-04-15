#!/usr/bin/env python3
"""
oqlos/shared/event_server.py — WebSocket event broker.

Broadcasts events between CLI, API, and browser clients.
Optional component — requires ``websockets`` (pip install oqlos[server]).

Usage:
    python -m oqlos.shared.event_server
    # or via entry point:
    oqlos-events --port 8104
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

try:
    import websockets
    from websockets.asyncio.server import serve, ServerConnection
except ImportError:
    websockets = None  # type: ignore

from oqlos.shared.event_store import EventStore


# ── Connection Manager ──────────────────────────────────────────────────────

class ConnectionManager:
    """Tracks connected WebSocket clients and broadcasts messages."""

    def __init__(self) -> None:
        self.active: set[ServerConnection] = set()
        self.client_info: dict[ServerConnection, dict] = {}

    async def connect(self, ws: ServerConnection, info: dict | None = None) -> None:
        self.active.add(ws)
        self.client_info[ws] = info or {}

    async def disconnect(self, ws: ServerConnection) -> None:
        self.active.discard(ws)
        self.client_info.pop(ws, None)

    async def broadcast(self, message: str, exclude: ServerConnection | None = None) -> None:
        for ws in list(self.active):
            if ws is exclude:
                continue
            try:
                await ws.send(message)
            except Exception:
                self.active.discard(ws)
                self.client_info.pop(ws, None)

    def get_stats(self) -> dict:
        return {
            "connections": len(self.active),
            "clients": [
                {"source": info.get("source", "?"), "path": info.get("path", "/")}
                for info in self.client_info.values()
            ],
        }


# ── Event Server ────────────────────────────────────────────────────────────

class EventServer:
    """WebSocket event broker with persistence."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8104, persist_path: str | None = None):
        self.host = host
        self.port = port
        self.manager = ConnectionManager()
        self.event_store = EventStore(persist_path=persist_path)

    async def handle_client(self, websocket: ServerConnection) -> None:
        path = websocket.request.path if websocket.request else "/"
        client_type = "browser" if path == "/browser" else "cli" if path == "/cli" else "unknown"

        await self.manager.connect(websocket, {
            "source": client_type,
            "path": path,
            "connected_at": datetime.now(timezone.utc).isoformat(),
        })

        try:
            recent = self.event_store.get_recent(50)
            if recent:
                await websocket.send(json.dumps({"type": "sync", "events": recent}))

            async for message in websocket:
                await self._handle_message(websocket, message)
        except Exception:
            pass
        finally:
            await self.manager.disconnect(websocket)

    async def _handle_message(self, sender: ServerConnection, message: str) -> None:
        try:
            data = json.loads(message)

            if data.get("type") == "ping":
                await sender.send(json.dumps({"type": "pong"}))
                return
            if data.get("type") == "stats":
                await sender.send(json.dumps({
                    "type": "stats",
                    **self.manager.get_stats(),
                    "events_count": self.event_store.count,
                }))
                return
            if data.get("type") == "clear":
                self.event_store.clear()
                await self.manager.broadcast(json.dumps({"type": "cleared"}))
                return

            event = self._normalize_event(data)
            self.event_store.append(event)
            await self.manager.broadcast(json.dumps(event), exclude=sender)

            source = self.manager.client_info.get(sender, {}).get("source", "?")
            print(f"📨 [{source}] {event.get('type', 'unknown')}: "
                  f"{json.dumps(event.get('payload', {}))[:80]}")

        except json.JSONDecodeError:
            print(f"⚠️  Invalid JSON: {message[:100]}")
        except Exception as e:
            print(f"❌ Error: {e}")

    @staticmethod
    def _normalize_event(data: Dict) -> Dict:
        if "id" not in data:
            data["id"] = f"evt-{int(time.time() * 1000):x}-{random.randint(0, 0xffff):04x}"
        if "timestamp" not in data:
            data["timestamp"] = datetime.now(timezone.utc).isoformat() + "Z"
        return data

    async def start(self) -> None:
        if websockets is None:
            print("❌ websockets not installed — pip install oqlos[server]")
            sys.exit(1)

        print(f"✅ OqlOS Event Server running on ws://{self.host}:{self.port}")
        async with serve(
            self.handle_client, self.host, self.port,
            ping_interval=30, ping_timeout=10,
        ) as server:
            await server.serve_forever()


def main() -> None:
    host = os.environ.get("OQLOS_EVENT_HOST", "0.0.0.0")
    port = int(os.environ.get("OQLOS_EVENT_PORT", "8104"))
    persist = os.environ.get("OQLOS_EVENT_PERSIST", None)

    server = EventServer(host, port, persist_path=persist)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\n👋 Server stopped")


if __name__ == "__main__":
    main()
