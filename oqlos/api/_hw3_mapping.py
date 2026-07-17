"""Routes: mapping, CQRS, oql-mapped-exec; plus hardware_events WebSocket handler."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

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
from oqlos.api.hardware_mapping_access import (
    MAP_BODY_SECTIONS,
    MappingAccessError,
    access_policy_document,
    assert_sections_writable,
    filter_mapping_for_persona,
    normalize_oql_persona,
    resolve_edit_persona,
    sections_owned_by,
    sections_writable_by,
)
from oqlos.api.hardware_mapping_contract import MAP_SCHEMA, MAPPING_CONTRACT_VERSION, MappingContractError
from oqlos.api.hardware_mapping_store import mapping_store, normalize_mapping

sub_router = APIRouter()


class MappingLayerPatchRequest(BaseModel):
    sections: dict[str, Any] = Field(default_factory=dict)
    persist: bool = True
    persona: str | None = None
    role: str | None = None


def _persona_from_request(
    *,
    persona: str | None = None,
    role: str | None = None,
    x_oql_edit_persona: str | None = None,
    x_connect_role: str | None = None,
) -> str:
    return resolve_edit_persona(
        persona=persona,
        role=role,
        header_persona=x_oql_edit_persona,
        header_role=x_connect_role,
    )


@sub_router.post("/runtime-python/resolve-func")
async def hardware_runtime_python_resolve_func_v3(req: RuntimeFuncResolveRequest) -> dict[str, Any]:
    usage_mode = req.usage_mode or req.usageMode
    try:
        hardware_map = normalize_mapping(req.hardware_map)
    except MappingContractError as exc:
        raise HTTPException(status_code=400, detail={"error": "Invalid hardware MAP", "issues": exc.issues}) from exc
    return _resolve_func_steps(hardware_map, req.func_name, req.environment, usage_mode)


@sub_router.get("/mapping/access-policy")
async def hardware_mapping_access_policy_v3() -> dict[str, Any]:
    return access_policy_document()


@sub_router.get("/mapping")
async def hardware_mapping_get_v3(
    persona: str | None = Query(default=None),
    role: str | None = Query(default=None),
    x_oql_edit_persona: str | None = Header(default=None, alias="X-Oql-Edit-Persona"),
    x_connect_role: str | None = Header(default=None, alias="X-Connect-Role"),
) -> dict[str, Any]:
    mapping = mapping_store.get()
    resolved = _persona_from_request(
        persona=persona,
        role=role,
        x_oql_edit_persona=x_oql_edit_persona,
        x_connect_role=x_connect_role,
    )
    view = filter_mapping_for_persona(mapping, resolved)
    return {
        "ok": True,
        "mapping": mapping,
        "access": {
            "persona": view["persona"],
            "editable_sections": view["editable_sections"],
            "owned_sections": view["owned_sections"],
            "locked_sections": view["locked_sections"],
        },
        "storage_backend": mapping_store.storage_backend,
        "database_key": None,
        "store_path": mapping_store.file_path,
        "contract": MAPPING_CONTRACT_VERSION,
    }


@sub_router.get("/mapping/schema")
async def hardware_mapping_schema_v3() -> dict[str, Any]:
    return {
        "ok": True,
        "contract": MAPPING_CONTRACT_VERSION,
        "schema": MAP_SCHEMA,
        "access": access_policy_document(),
    }


@sub_router.put("/mapping")
async def hardware_mapping_put_v3(
    req: MappingReplaceRequest,
    x_oql_edit_persona: str | None = Header(default=None, alias="X-Oql-Edit-Persona"),
    x_connect_role: str | None = Header(default=None, alias="X-Connect-Role"),
) -> dict[str, Any]:
    persona = _persona_from_request(
        persona=getattr(req, "persona", None),
        role=getattr(req, "role", None),
        x_oql_edit_persona=x_oql_edit_persona,
        x_connect_role=x_connect_role,
    )
    explicit = bool(
        getattr(req, "persona", None)
        or getattr(req, "role", None)
        or x_oql_edit_persona
        or x_connect_role
    )
    # Full document replace: system or administrator tools (import/restore).
    # Day-to-day edits should use PATCH /mapping/layer/{persona}.
    if explicit and persona not in {"system", "administrator"}:
        raise HTTPException(
            status_code=403,
            detail={
                "error": f"Full MAP replace requires persona 'system' or 'administrator' (got '{persona}')",
                "issues": ["use PATCH /api/v3/hardware/mapping/layer/{persona}"],
                "persona": persona,
            },
        )
    try:
        mapping = mapping_store.replace(req.mapping, persist=req.persist)
    except MappingContractError as exc:
        raise HTTPException(status_code=400, detail={"error": "Invalid hardware MAP", "issues": exc.issues}) from exc
    return {
        "ok": True,
        "mapping": mapping,
        "persisted": req.persist,
        "persona": persona if explicit else "system",
    }


@sub_router.patch("/mapping/layer/{persona}")
async def hardware_mapping_patch_layer_v3(
    persona: str,
    req: MappingLayerPatchRequest,
    x_oql_edit_persona: str | None = Header(default=None, alias="X-Oql-Edit-Persona"),
    x_connect_role: str | None = Header(default=None, alias="X-Connect-Role"),
) -> dict[str, Any]:
    resolved = _persona_from_request(
        persona=req.persona or persona,
        role=req.role,
        x_oql_edit_persona=x_oql_edit_persona,
        x_connect_role=x_connect_role,
    )
    path_persona = normalize_oql_persona(persona)
    if path_persona and path_persona != resolved and resolved != "system":
        owned = set(sections_owned_by(path_persona))
        writable = set(sections_writable_by(resolved))
        if not owned.issubset(writable):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": f"Persona '{resolved}' cannot edit layer '{path_persona}'",
                    "persona": resolved,
                    "layer": path_persona,
                },
            )
    section_keys = [k for k in req.sections.keys() if k in MAP_BODY_SECTIONS]
    if not section_keys:
        section_keys = list(sections_owned_by(path_persona or resolved))
    try:
        assert_sections_writable(resolved, section_keys, role=req.role or x_connect_role)
        mapping = mapping_store.merge_sections(
            req.sections,
            sections=section_keys,
            persist=req.persist,
        )
    except MappingAccessError as exc:
        raise HTTPException(
            status_code=403,
            detail={"error": str(exc), "issues": exc.issues, "persona": resolved},
        ) from exc
    except MappingContractError as exc:
        raise HTTPException(status_code=400, detail={"error": "Invalid hardware MAP", "issues": exc.issues}) from exc
    return {
        "ok": True,
        "mapping": mapping,
        "persisted": req.persist,
        "persona": resolved,
        "updated_sections": section_keys,
    }


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
