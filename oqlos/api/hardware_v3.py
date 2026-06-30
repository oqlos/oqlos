"""Compatibility API for hardware UI moved from c2004 into OqlOS.

The browser keeps using the established ``/api/v3/hardware/*`` paths, but the
implementation is now OqlOS-owned and dispatches directly to the local hardware
gateway/plugin layer.
"""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from fastapi import APIRouter, Body, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

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
from oqlos.hardware.transport.manage_ops import run_manage_verb

router = APIRouter(prefix="/api/v3/hardware", tags=["hardware-v3-compat"])

_scanner_last: dict[str, Any] | None = None

_PERIPHERAL_ALIASES = {
    "dri0050": "motor-dri0050",
    "motor_dri0050": "motor-dri0050",
    "pump": "motor-dri0050",
    "tic249": "motor-tic249",
    "motor_tic249": "motor-tic249",
    "stepper": "motor-tic249",
    "lung": "artificial-lung",
    "lung-main": "artificial-lung",
    "modbus_io": "modbus-io",
    "waveshare-io": "modbus-io",
    "modbus_adc": "modbus-adc",
    "waveshare-adc": "modbus-adc",
    "piadc": "modbus-adc",
    "scanner": "barcode-scanner",
    "barcode": "barcode-scanner",
}


class DiagnosticCommandRequest(BaseModel):
    peripheral_id: str
    command: str
    args: dict[str, Any] = {}


class MappingReplaceRequest(BaseModel):
    mapping: dict[str, Any]
    persist: bool = True


class MappingImportRequest(BaseModel):
    content: str
    format: Literal["json", "yaml"] = "yaml"
    persist: bool = True


class MappingExportRequest(BaseModel):
    format: Literal["json", "yaml"] = "yaml"


class MappingResetRequest(BaseModel):
    persist: bool = True


class RuntimeFuncResolveRequest(BaseModel):
    hardware_map: dict[str, Any]
    func_name: str
    environment: str | None = None
    usage_mode: str | None = None
    usageMode: str | None = None


class CqrsCommandRequest(BaseModel):
    command: dict[str, Any]


class CqrsEventsClearRequest(BaseModel):
    truncate_persistent: bool = False


class ScannerIngestRequest(BaseModel):
    code: str
    source: str = "manual"
    symbology: str | None = None
    metadata: dict[str, Any] | None = None


def normalize_peripheral_id(value: str) -> str:
    token = str(value or "").strip().lower().replace("_", "-")
    return _PERIPHERAL_ALIASES.get(token, token)


def _ok_from_result(result: Any) -> bool:
    if not isinstance(result, dict):
        return bool(result)
    if "ok" in result:
        return bool(result["ok"])
    if "success" in result:
        return bool(result["success"])
    if "compatible" in result:
        return bool(result["compatible"])
    return not bool(result.get("error"))


def _runtime_control_skipped(action: str, **extra: object) -> dict[str, object]:
    return {
        "ok": True,
        "skipped": True,
        "action": action,
        "transport": "direct-oqlos",
        "runtime_control_available": False,
        "oqlos_up": True,
        "message": "Runtime control is disabled inside OqlOS; this process owns the hardware gateway.",
        **extra,
    }


def _find_adapter(identify_payload: dict[str, Any], peripheral_id: str) -> dict[str, Any] | None:
    for adapter in identify_payload.get("adapters") or []:
        if isinstance(adapter, dict) and adapter.get("id") == peripheral_id:
            return adapter
    return None


async def _run_diagnostic(peripheral_id: str, command: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized = normalize_peripheral_id(peripheral_id)
    payload = {
        "peripheral_id": normalized,
        "command": str(command or "").strip(),
        "args": args if isinstance(args, dict) else {},
    }
    if normalized == "artificial-lung":
        result = await run_manage_verb(
            "artificial-lung-command",
            {"payload": {"command": payload["command"], "args": payload["args"]}},
        )
    elif normalized == "rtc":
        result = await run_manage_verb(
            "rtc-command",
            {"payload": {"command": payload["command"], "args": payload["args"]}},
        )
    else:
        result = await run_manage_verb("diagnostic-command", payload)

    if not isinstance(result, dict):
        result = {"result": result}
    result.setdefault("ok", _ok_from_result(result))
    result.setdefault("peripheral_id", normalized)
    result.setdefault("command", payload["command"])
    result.setdefault("transport", "direct-oqlos")
    await publish_hardware_command_event({"payload": payload}, result, context={"source": "diagnostic-command"})
    return result


def _resolve_func_steps(
    hardware_map: dict[str, Any],
    func_name: str,
    environment: str | None,
    usage_mode: str | None,
) -> dict[str, Any]:
    funcs = hardware_map.get("funcImplementations") if isinstance(hardware_map, dict) else None
    if not isinstance(funcs, dict):
        return {"ok": False, "error": "hardware_map.funcImplementations must be an object"}
    func = funcs.get(func_name)
    if not isinstance(func, dict):
        return {"ok": False, "error": f"FUNC '{func_name}' not found"}

    object_map = hardware_map.get("objectActionMap") if isinstance(hardware_map.get("objectActionMap"), dict) else {}
    actions = hardware_map.get("actions") if isinstance(hardware_map.get("actions"), dict) else {}
    resolved_steps: list[dict[str, Any]] = []
    for step in func.get("steps") or []:
        if not isinstance(step, dict):
            continue
        object_name = step.get("object")
        action_name = step.get("action")
        binding = None
        if object_name and isinstance(object_map.get(object_name), dict):
            binding = object_map[object_name].get(action_name)
        if binding is None and action_name:
            binding = actions.get(action_name)
        resolved_steps.append(
            {
                "step": step,
                "binding": binding if isinstance(binding, dict) else None,
                "resolved": isinstance(binding, dict),
            }
        )

    return {
        "ok": True,
        "func_name": func_name,
        "environment": environment,
        "usage_mode": usage_mode,
        "implementation": func,
        "steps": resolved_steps,
    }


@router.get("/health")
async def hardware_health_v3() -> dict[str, Any]:
    from oqlos.api import hardware as hw

    payload = await hw.hardware_health()
    if isinstance(payload, dict):
        payload.setdefault("ok", payload.get("overall_ok", True))
        payload.setdefault("transport", "direct-oqlos")
    return payload


@router.get("/identify")
async def hardware_identify_v3(scan: str = "never") -> dict[str, Any]:
    from oqlos.api import hardware as hw

    return await hw.hardware_identify(scan=scan or "never")


@router.get("/proxy-info")
async def hardware_proxy_info_v3() -> dict[str, Any]:
    return {
        "ok": True,
        "transport": "direct-oqlos",
        "proxy": False,
        "service": "oqlos-hardware-api",
        "api_prefix": "/api/v3/hardware",
        "native_prefix": "/api/v1/hardware",
    }


@router.get("/peripheral-status/{peripheral_id}")
async def hardware_peripheral_status_v3(peripheral_id: str) -> dict[str, Any]:
    normalized = normalize_peripheral_id(peripheral_id)
    if normalized == "artificial-lung":
        result = await run_manage_verb("artificial-lung-status")
        return {
            "ok": _ok_from_result(result),
            "peripheral_id": normalized,
            "command": "status",
            "result": result,
            "transport": "direct-oqlos",
        }
    if normalized == "rtc":
        result = await run_manage_verb("rtc-status")
        return {
            "ok": _ok_from_result(result),
            "peripheral_id": normalized,
            "command": "status",
            "result": result,
            "transport": "direct-oqlos",
        }
    if normalized == "barcode-scanner":
        identify = await hardware_identify_v3(scan="never")
        adapter = _find_adapter(identify, normalized)
        return {
            "ok": bool(adapter and adapter.get("status") == "ok"),
            "peripheral_id": normalized,
            "command": "scanner_status",
            "result": adapter or {},
            "status": adapter.get("status") if adapter else "unknown",
            "transport": "direct-oqlos",
        }
    try:
        return await _run_diagnostic(normalized, "status", {})
    except Exception as exc:
        identify = await hardware_identify_v3(scan="never")
        adapter = _find_adapter(identify, normalized)
        return {
            "ok": bool(adapter and adapter.get("status") == "ok"),
            "peripheral_id": normalized,
            "command": "status",
            "result": adapter or {},
            "status": adapter.get("status") if adapter else "unknown",
            "error": str(exc),
            "transport": "direct-oqlos",
        }


@router.post("/diagnostic-command")
async def hardware_diagnostic_command_v3(req: DiagnosticCommandRequest) -> dict[str, Any]:
    try:
        return await _run_diagnostic(req.peripheral_id, req.command, req.args)
    except HTTPException:
        raise
    except Exception as exc:
        payload = {
            "peripheral_id": normalize_peripheral_id(req.peripheral_id),
            "command": req.command,
            "args": req.args,
        }
        result = {
            "ok": False,
            "success": False,
            "error": str(exc),
            "peripheral_id": payload["peripheral_id"],
            "command": req.command,
            "transport": "direct-oqlos",
        }
        await publish_hardware_command_event({"payload": payload}, result, context={"source": "diagnostic-command"})
        return result


@router.get("/hui/actions")
async def hardware_hui_actions_v3() -> dict[str, Any]:
    from oqlos.api import hardware as hw

    return await hw.hui_actions()


@router.post("/hui/shutdown")
async def hardware_hui_shutdown_v3(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    from oqlos.api import hardware as hw

    return await hw.hui_shutdown()


@router.post("/hui/hold/{key}/start")
async def hardware_hui_hold_start_v3(key: str, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    from oqlos.api import hardware as hw

    return await hw.hui_hold_start(key)


@router.post("/hui/hold/{key}/stop")
async def hardware_hui_hold_stop_v3(key: str, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    from oqlos.api import hardware as hw

    return await hw.hui_hold_stop(key)


@router.post("/hui/al/{command}")
async def hardware_hui_al_command_v3(command: str, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    from oqlos.api import hardware as hw

    normalized = command.strip().lower()
    if normalized == "start":
        return await hw.hui_al_start()
    if normalized == "stop":
        return await hw.hui_al_stop()
    raise HTTPException(status_code=400, detail=f"Unsupported HUI AL command: {command}")


@router.post("/modbus/autoconfigure")
async def hardware_modbus_autoconfigure_v3() -> dict[str, Any]:
    from oqlos.api import hardware as hw

    return await hw.hardware_recover_route(scope="safe")


@router.get("/diagnosis")
async def hardware_diagnosis_v3() -> dict[str, Any]:
    from oqlos.api import hardware as hw

    return await hw.hardware_diagnosis_route(scan="never")


@router.post("/diagnosis/repair")
async def hardware_diagnosis_repair_v3() -> dict[str, Any]:
    from oqlos.api import hardware as hw

    return await hw.hardware_recover_route(scope="safe")


@router.get("/modbus/waveshare-diagnose")
async def hardware_modbus_waveshare_diagnose_v3(exclusive: bool = False) -> dict[str, Any]:
    from oqlos.api import hardware as hw

    return await hw.hardware_modbus_waveshare_diagnose()


@router.get("/modbus/wizard/plan")
async def hardware_modbus_wizard_plan_v3() -> dict[str, Any]:
    from oqlos.api import hardware as hw

    return await hw.hardware_modbus_wizard_plan()


@router.get("/stack/snapshot")
async def hardware_stack_snapshot_v3() -> dict[str, Any]:
    from oqlos.api import hardware as hw

    return await hw.hardware_stack_snapshot()


@router.get("/runtime/status")
async def hardware_runtime_status_v3(serial_port: str = "") -> dict[str, object]:
    return _runtime_control_skipped("status", serial_port=serial_port)


@router.post("/runtime/stop")
async def hardware_runtime_stop_v3(payload: dict[str, object] = Body(default_factory=dict)) -> dict[str, object]:
    return _runtime_control_skipped("stop", serial_port=str(payload.get("serial_port") or ""))


@router.post("/runtime/start")
async def hardware_runtime_start_v3(payload: dict[str, object] = Body(default_factory=dict)) -> dict[str, object]:
    return _runtime_control_skipped("start", mode=str(payload.get("mode") or "light"))


@router.post("/runtime/make")
async def hardware_runtime_make_v3(payload: dict[str, object] = Body(default_factory=dict)) -> dict[str, object]:
    return _runtime_control_skipped("make", target=str(payload.get("target") or ""))


@router.post("/modbus/wizard/probe-isolated")
async def hardware_modbus_wizard_probe_isolated_v3(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    from oqlos.api import hardware as hw

    return await hw.hardware_modbus_wizard_probe_isolated(
        serial_port=str(payload.get("serial_port") or ""),
        baudrates=payload.get("baudrates") if isinstance(payload.get("baudrates"), list) else None,
        parities=payload.get("parities") if isinstance(payload.get("parities"), list) else None,
        device_ids=payload.get("device_ids") if isinstance(payload.get("device_ids"), list) else None,
        module_role=str(payload.get("module_role") or ""),
    )


@router.post("/modbus/wizard/program-isolated")
async def hardware_modbus_wizard_program_isolated_v3(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    from oqlos.api import hardware as hw

    return await hw.hardware_modbus_wizard_program_isolated(
        serial_port=str(payload.get("serial_port") or ""),
        current_device_id=int(payload.get("current_device_id") or 1),
        new_device_id=int(payload.get("new_device_id") or 1),
        new_baudrate=int(payload.get("new_baudrate") or 9600),
        new_parity=str(payload.get("new_parity") or "N"),
        confirm_isolated=bool(payload.get("confirm_isolated")),
    )


@router.post("/runtime-python")
async def hardware_runtime_python_v3(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    return {
        "ok": False,
        "error": "runtime-python execution moved out of c2004 is not enabled in OqlOS",
        "received": payload,
    }


@router.post("/runtime-python/resolve-func")
async def hardware_runtime_python_resolve_func_v3(req: RuntimeFuncResolveRequest) -> dict[str, Any]:
    usage_mode = req.usage_mode or req.usageMode
    try:
        hardware_map = normalize_mapping(req.hardware_map)
    except MappingContractError as exc:
        raise HTTPException(status_code=400, detail={"error": "Invalid hardware MAP", "issues": exc.issues}) from exc
    return _resolve_func_steps(hardware_map, req.func_name, req.environment, usage_mode)


@router.get("/mapping")
async def hardware_mapping_get_v3() -> dict[str, Any]:
    return {
        "ok": True,
        "mapping": mapping_store.get(),
        "storage_backend": mapping_store.storage_backend,
        "database_key": None,
        "store_path": mapping_store.file_path,
        "contract": MAPPING_CONTRACT_VERSION,
    }


@router.get("/mapping/schema")
async def hardware_mapping_schema_v3() -> dict[str, Any]:
    return {"ok": True, "contract": MAPPING_CONTRACT_VERSION, "schema": MAP_SCHEMA}


@router.put("/mapping")
async def hardware_mapping_put_v3(req: MappingReplaceRequest) -> dict[str, Any]:
    try:
        mapping = mapping_store.replace(req.mapping, persist=req.persist)
    except MappingContractError as exc:
        raise HTTPException(status_code=400, detail={"error": "Invalid hardware MAP", "issues": exc.issues}) from exc
    return {"ok": True, "mapping": mapping, "persisted": req.persist}


@router.post("/mapping/import")
async def hardware_mapping_import_v3(req: MappingImportRequest) -> dict[str, Any]:
    try:
        mapping = mapping_store.import_text(req.content, req.format, persist=req.persist)
    except MappingContractError as exc:
        raise HTTPException(status_code=400, detail={"error": "Invalid hardware MAP", "issues": exc.issues}) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "mapping": mapping, "format": req.format, "persisted": req.persist}


@router.post("/mapping/export")
async def hardware_mapping_export_v3(req: MappingExportRequest) -> dict[str, Any]:
    try:
        content = mapping_store.export_text(req.format)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "format": req.format, "content": content}


@router.post("/mapping/reset")
async def hardware_mapping_reset_v3(req: MappingResetRequest) -> dict[str, Any]:
    mapping = mapping_store.reset(persist=req.persist)
    return {"ok": True, "mapping": mapping, "persisted": req.persist}


@router.post("/oql-mapped-exec")
async def hardware_oql_mapped_exec_v3(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    try:
        hardware_map = normalize_mapping(payload.get("hardware_map")) if isinstance(payload.get("hardware_map"), dict) else mapping_store.get()
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


@router.post("/cqrs/command")
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


@router.get("/cqrs/events")
async def hardware_cqrs_events_v3(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    events = list_hardware_command_events(limit)
    return {"ok": True, "count": len(events), "events": events, "store_path": get_hardware_command_event_store_path()}


@router.post("/cqrs/events/clear")
async def hardware_cqrs_events_clear_v3(req: CqrsEventsClearRequest) -> dict[str, Any]:
    clear_hardware_command_events(truncate_persistent=req.truncate_persistent)
    return {"ok": True, "cleared": True, "store_path": get_hardware_command_event_store_path()}


@router.get("/scanner/status")
async def hardware_scanner_status_v3() -> dict[str, Any]:
    peripheral = await hardware_peripheral_status_v3("barcode-scanner")
    detail = peripheral.get("result") if isinstance(peripheral.get("result"), dict) else {}
    adapter_status = str(peripheral.get("status") or "unknown")
    present = bool(detail.get("scanner_present")) or adapter_status == "ok"
    return {
        "success": True,
        "data": {
            "status": "online" if adapter_status == "ok" else "offline",
            "scanner_present": present,
            "last_scan": _scanner_last,
            "source": "oqlos-identify",
            "detail": detail,
        },
    }


@router.get("/scanner/last")
async def hardware_scanner_last_v3() -> dict[str, Any]:
    return {"success": True, "data": _scanner_last, "source": "oqlos-local"}


@router.post("/scanner/ingest")
async def hardware_scanner_ingest_v3(payload: ScannerIngestRequest) -> dict[str, Any]:
    global _scanner_last
    from datetime import datetime, timezone

    _scanner_last = {
        "code": payload.code,
        "source": payload.source,
        "symbology": payload.symbology,
        "metadata": payload.metadata or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return {"success": True, "data": _scanner_last, "source": "oqlos-local"}


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
