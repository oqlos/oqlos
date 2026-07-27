"""Hardware CQRS audit endpoints and event WebSocket.

Kept separate from retired compatibility routes so mounting
the audit stream cannot accidentally re-enable legacy configuration APIs.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from oqlos.api._hw3_models import CqrsCommandRequest, CqrsEventsClearRequest, _run_diagnostic, normalize_peripheral_id
from oqlos.api.hardware_events import (
    clear_hardware_command_events,
    get_hardware_command_event_store_path,
    list_hardware_command_events,
    publish_hardware_command_event,
    subscribe_hardware_command_events,
    unsubscribe_hardware_command_events,
)
from oqlos.errors import OqlosError

router = APIRouter()


@router.post("/cqrs/command")
async def hardware_cqrs_command_v3(req: CqrsCommandRequest) -> dict[str, Any]:
    command = req.command if isinstance(req.command, dict) else {}
    payload = command.get("payload") if isinstance(command.get("payload"), dict) else command
    peripheral_id = normalize_peripheral_id(str(payload.get("peripheral_id") or payload.get("peripheralId") or ""))
    command_name = str(payload.get("command") or payload.get("command_name") or "").strip()
    args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
    if not peripheral_id or not command_name:
        result = {
            "ok": False,
            "error": "CQRS command requires peripheral_id and command",
            "command": command,
        }
        await publish_hardware_command_event(
            command, result, context={"source": "hardware-cqrs-command-endpoint"}
        )
        raise OqlosError(
            code="api_modbus_wizard_invalid_request",
            status_code=422,
            message="CQRS command requires peripheral_id and command",
            detail={"command": command},
        )
    result = await _run_diagnostic(peripheral_id, command_name, args)
    return {"ok": True, "command": command, "result": result}


@router.get("/cqrs/events")
async def hardware_cqrs_events_v3(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    events = list_hardware_command_events(limit)
    return {"ok": True, "count": len(events), "events": events, "store_path": get_hardware_command_event_store_path()}


@router.post("/cqrs/events/clear")
async def hardware_cqrs_events_clear_v3(req: CqrsEventsClearRequest) -> dict[str, Any]:
    clear_hardware_command_events(truncate_persistent=req.truncate_persistent)
    return {"ok": True, "cleared": True, "store_path": get_hardware_command_event_store_path()}


async def hardware_events_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    subscriber_id, queue = subscribe_hardware_command_events(max_queue_size=200)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json({"message_type": "event", "data": event})
            except asyncio.TimeoutError:
                await websocket.send_json({"message_type": "heartbeat"})
    except WebSocketDisconnect:
        return
    finally:
        unsubscribe_hardware_command_events(subscriber_id)
