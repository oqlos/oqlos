"""
oqlos.api.oql_mqtt — HTTP/WS surface for the OQL-over-MQTT transport.

Exposes ``POST /api/v1/oql/execute`` and ``WS /ws/oql`` (mounted in
``oqlos.api.main``). Both dispatch OQL through a process-global
:class:`~oqlos.hardware.transport.mqtt_oql_bridge.OqlMqttController` that is
created in the app lifespan when ``OQLOS_OQL_TRANSPORT_ROLE`` selects a
controller. When no controller is configured the endpoints return 503.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from oqlos.errors import OqlosError
from oqlos.hardware.transport.mqtt_oql_bridge import OqlMqttController

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/oql", tags=["oql"])

_controller: OqlMqttController | None = None


def set_oql_controller(controller: OqlMqttController | None) -> None:
    """Install (or clear) the process-global controller used by the routes."""
    global _controller
    _controller = controller


def get_oql_controller() -> OqlMqttController | None:
    return _controller


class OqlExecuteRequest(BaseModel):
    oql: str
    kind: str = "command"  # "command" | "script" | "manage" | "ping"
    mode: str = "execute"
    node_id: str | None = None  # reserved for multi-node routing
    sensors: dict[str, float] | None = None
    args: dict[str, Any] | None = None  # parameters when kind == "manage"
    skip_waits: bool = False
    timeout_ms: int | None = Field(default=None, ge=1)


class OqlManageRequest(BaseModel):
    verb: str
    args: dict[str, Any] | None = None
    timeout_ms: int | None = Field(default=None, ge=1)


class OqlExecuteResponse(BaseModel):
    ok: bool
    result: dict[str, Any] | None = None
    error: str | None = None
    node_id: str = ""


@router.post("/execute", response_model=OqlExecuteResponse)
async def execute_oql(req: OqlExecuteRequest) -> OqlExecuteResponse:
    if _controller is None:
        raise OqlosError(code="api_oql_transport_disabled", status_code=503)
    timeout = (req.timeout_ms / 1000.0) if req.timeout_ms else None
    resp = await _controller.execute(
        req.oql,
        kind=req.kind,
        mode=req.mode,
        sensors=req.sensors,
        args=req.args,
        skip_waits=req.skip_waits,
        timeout=timeout,
        source="api",
    )
    return OqlExecuteResponse(ok=resp.ok, result=resp.result, error=resp.error, node_id=resp.node_id)


@router.post("/manage", response_model=OqlExecuteResponse)
async def manage_hardware(req: OqlManageRequest) -> OqlExecuteResponse:
    """Run a remote management/diagnostic verb over MQTT.

    Verbs: identify, health, diagnose, diagnosis, recover, stack-snapshot,
    waveshare-diagnose, wizard-plan, wizard-probe, wizard-program, valve, pump,
    sensor, lung, lung-stop, lung-disable, rtc-status, rtc-command, temperature.
    """
    if _controller is None:
        raise OqlosError(code="api_oql_transport_disabled", status_code=503)
    timeout = (req.timeout_ms / 1000.0) if req.timeout_ms else None
    resp = await _controller.manage(req.verb, req.args, timeout=timeout)
    return OqlExecuteResponse(ok=resp.ok, result=resp.result, error=resp.error, node_id=resp.node_id)


@router.websocket("/ws")
async def oql_ws(websocket: WebSocket) -> None:
    """Bidirectional OQL channel: client sends OQL frames, receives results.

    Inbound frame: ``{"oql": "...", "kind": "command", "mode": "execute"}``.
    Outbound: the execute result, plus a live ``{"event": ...}`` stream from the
    remote agent.
    """
    await websocket.accept()
    if _controller is None:
        await websocket.send_json({"error": "OQL MQTT transport is disabled (role=off)"})
        await websocket.close(code=1011)
        return

    event_queue = _controller.subscribe_events()
    pump_task = asyncio.create_task(_pump_events(websocket, event_queue))
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "invalid JSON"})
                continue
            oql = msg.get("oql")
            if not oql:
                await websocket.send_json({"error": "missing 'oql'"})
                continue
            resp = await _controller.execute(
                oql,
                kind=msg.get("kind", "command"),
                mode=msg.get("mode", "execute"),
                sensors=msg.get("sensors"),
                skip_waits=bool(msg.get("skip_waits", False)),
                source="ws",
            )
            await websocket.send_json(
                {"ok": resp.ok, "result": resp.result, "error": resp.error, "node_id": resp.node_id}
            )
    except WebSocketDisconnect:
        pass
    finally:
        pump_task.cancel()
        _controller.unsubscribe_events(event_queue)


async def _pump_events(websocket: WebSocket, queue: asyncio.Queue) -> None:
    try:
        while True:
            event = await queue.get()
            await websocket.send_json({"event": event})
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception:  # pragma: no cover - defensive
        logger.debug("OQL ws event pump stopped", exc_info=True)
