"""Routes: mapping, CQRS, oql-mapped-exec; plus hardware_events WebSocket handler."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, WebSocket, WebSocketDisconnect

from oqlos.api._hw3_models import (
    CqrsCommandRequest,
    CqrsEventsClearRequest,
    MappingExportRequest,
    MappingImportRequest,
    MappingReplaceRequest,
    MappingResetRequest,
    RuntimeFuncResolveRequest,
    _resolve_func_steps,
    _run_diagnostic,
    normalize_peripheral_id,
)
from oqlos.api.hardware_events import (
    clear_hardware_command_events,
    get_hardware_command_event_store_path,
    list_hardware_command_events,
    publish_hardware_command_event,
    subscribe_hardware_command_events,
    unsubscribe_hardware_command_events,
)
from oqlos.api.hardware_mapping_contract import MAP_SCHEMA, MAPPING_CONTRACT_VERSION, MappingContractError
from oqlos.api.hardware_mapping_store import mapping_store, normalize_mapping

sub_router = APIRouter()


@sub_router.post("/runtime-python/resolve-func")
async def hardware_runtime_python_resolve_func_v3(req: RuntimeFuncResolveRequest) -> dict[str, Any]:
    usage_mode = req.usage_mode or req.usageMode
    try:
        hardware_map = normalize_mapping(req.hardware_map)
    except MappingContractError as exc:
        raise HTTPException(status_code=400, detail={"error": "Invalid hardware MAP", "issues": exc.issues}) from exc
    return _resolve_func_steps(hardware_map, req.func_name, req.environment, usage_mode)


@sub_router.get("/mapping")
async def hardware_mapping_get_v3() -> dict[str, Any]:
    return {
        "ok": True,
        "mapping": mapping_store.get(),
        "storage_backend": mapping_store.storage_backend,
        "database_key": None,
        "store_path": mapping_store.file_path,
        "contract": MAPPING_CONTRACT_VERSION,
    }


@sub_router.get("/mapping/schema")
async def hardware_mapping_schema_v3() -> dict[str, Any]:
    return {"ok": True, "contract": MAPPING_CONTRACT_VERSION, "schema": MAP_SCHEMA}


@sub_router.put("/mapping")
async def hardware_mapping_put_v3(req: MappingReplaceRequest) -> dict[str, Any]:
    try:
        mapping = mapping_store.replace(req.mapping, persist=req.persist)
    except MappingContractError as exc:
        raise HTTPException(status_code=400, detail={"error": "Invalid hardware MAP", "issues": exc.issues}) from exc
    return {"ok": True, "mapping": mapping, "persisted": req.persist}


@sub_router.post("/mapping/import")
async def hardware_mapping_import_v3(req: MappingImportRequest) -> dict[str, Any]:
    try:
        mapping = mapping_store.import_text(req.content, req.format, persist=req.persist)
    except MappingContractError as exc:
        raise HTTPException(status_code=400, detail={"error": "Invalid hardware MAP", "issues": exc.issues}) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "mapping": mapping, "format": req.format, "persisted": req.persist}


@sub_router.post("/mapping/export")
async def hardware_mapping_export_v3(req: MappingExportRequest) -> dict[str, Any]:
    try:
        content = mapping_store.export_text(req.format)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "format": req.format, "content": content}


@sub_router.post("/mapping/reset")
async def hardware_mapping_reset_v3(req: MappingResetRequest) -> dict[str, Any]:
    mapping = mapping_store.reset(persist=req.persist)
    return {"ok": True, "mapping": mapping, "persisted": req.persist}


@sub_router.post("/oql-mapped-exec")
async def hardware_oql_mapped_exec_v3(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    try:
        hardware_map = (
            normalize_mapping(payload.get("hardware_map"))
            if isinstance(payload.get("hardware_map"), dict)
            else mapping_store.get()
        )
    except MappingContractError as exc:
        raise HTTPException(status_code=400, detail={"error": "Invalid hardware MAP", "issues": exc.issues}) from exc
    return {
        "ok": True,
        "dry_run": True,
        "source": "oqlos-oql-mapped-exec",
        "text": payload.get("text", ""),
        "hardware_map": hardware_map,
        "message": "Mapped OQL execution endpoint is present; direct actuation should use /api/v1/oql/execute.",
    }


@sub_router.post("/cqrs/command")
async def hardware_cqrs_command_v3(req: CqrsCommandRequest) -> dict[str, Any]:
    command = req.command if isinstance(req.command, dict) else {}
    payload = command.get("payload") if isinstance(command.get("payload"), dict) else command
    peripheral_id = normalize_peripheral_id(str(payload.get("peripheral_id") or payload.get("peripheralId") or ""))
    command_name = str(payload.get("command") or payload.get("command_name") or "").strip()
    args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
    if peripheral_id and command_name:
        result = await _run_diagnostic(peripheral_id, command_name, args)
    else:
        result = {"ok": False, "error": "CQRS command requires peripheral_id and command", "command": command}
        await publish_hardware_command_event(command, result, context={"source": "hardware-cqrs-command-endpoint"})
    return {"ok": True, "command": command, "result": result}


@sub_router.get("/cqrs/events")
async def hardware_cqrs_events_v3(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    events = list_hardware_command_events(limit)
    return {"ok": True, "count": len(events), "events": events, "store_path": get_hardware_command_event_store_path()}


@sub_router.post("/cqrs/events/clear")
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
