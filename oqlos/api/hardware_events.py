"""Recent hardware command events for the moved MAP editor."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

_recent_events: deque[dict[str, Any]] = deque(maxlen=500)
_subscribers: dict[str, asyncio.Queue[dict[str, Any]]] = {}


def _default_path() -> Path:
    configured = os.environ.get("OQLOS_HARDWARE_EVENTS_FILE") or os.environ.get("HARDWARE_EVENTS_FILE")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "oqlos" / "hardware-events.jsonl"


_event_store_path = _default_path()


def _load_recent_events_from_disk() -> None:
    _recent_events.clear()
    if not _event_store_path.exists():
        return
    try:
        lines = _event_store_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for raw in lines[-500:]:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            _recent_events.append(value)


def _append_event_to_disk(event: dict[str, Any]) -> None:
    try:
        _event_store_path.parent.mkdir(parents=True, exist_ok=True)
        with _event_store_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False))
            fh.write("\n")
    except OSError:
        return


def _broadcast_event_to_subscribers(event: dict[str, Any]) -> None:
    for queue in list(_subscribers.values()):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                continue


async def publish_hardware_command_event(
    command: dict[str, Any],
    result: dict[str, Any] | None,
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = command.get("payload") if isinstance(command.get("payload"), dict) else command
    event_payload = {
        "command": command,
        "result": result or {},
        "context": context or {},
    }
    peripheral_id = str(payload.get("peripheral_id") or payload.get("peripheralId") or "").strip()
    command_name = str(payload.get("command") or payload.get("command_name") or "").strip()
    if peripheral_id:
        event_payload["peripheral_id"] = peripheral_id
    if command_name:
        event_payload["command_name"] = command_name

    event = {
        "id": uuid4().hex,
        "source": "oqlos-hardware-api",
        "event_type": "hardware.command_executed",
        "aggregate_id": peripheral_id or None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": event_payload,
    }
    _recent_events.append(event)
    _append_event_to_disk(event)
    _broadcast_event_to_subscribers(event)
    return event


def list_hardware_command_events(limit: int = 50) -> list[dict[str, Any]]:
    cap = max(1, min(int(limit), 500))
    if not _recent_events:
        _load_recent_events_from_disk()
    return list(_recent_events)[-cap:]


def clear_hardware_command_events(*, truncate_persistent: bool = False) -> None:
    _recent_events.clear()
    if truncate_persistent:
        try:
            _event_store_path.parent.mkdir(parents=True, exist_ok=True)
            _event_store_path.write_text("", encoding="utf-8")
        except OSError:
            return


def get_hardware_command_event_store_path() -> str:
    return str(_event_store_path)


def subscribe_hardware_command_events(*, max_queue_size: int = 100) -> tuple[str, asyncio.Queue[dict[str, Any]]]:
    subscriber_id = uuid4().hex
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=max(1, int(max_queue_size)))
    _subscribers[subscriber_id] = queue
    return subscriber_id, queue


def unsubscribe_hardware_command_events(subscriber_id: str) -> None:
    _subscribers.pop(subscriber_id, None)


_load_recent_events_from_disk()
