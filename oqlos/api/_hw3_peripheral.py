"""Routes: /peripheral-status, /diagnostic-command, /scanner/*."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from oqlos.api._hw3_models import (
    DiagnosticCommandRequest,
    ScannerIngestRequest,
    _find_adapter,
    _ok_from_result,
    _run_diagnostic,
    normalize_peripheral_id,
)
from oqlos.api.hardware_events import publish_hardware_command_event

sub_router = APIRouter()

_scanner_last: dict[str, Any] | None = None


@sub_router.get("/peripheral-status/{peripheral_id}")
async def hardware_peripheral_status_v3(peripheral_id: str) -> dict[str, Any]:
    normalized = normalize_peripheral_id(peripheral_id)
    if normalized == "artificial-lung":
        from oqlos.hardware.transport.manage_ops import run_manage_verb
        result = await run_manage_verb("artificial-lung-status")
        return {
            "ok": _ok_from_result(result),
            "peripheral_id": normalized,
            "command": "status",
            "result": result,
            "transport": "direct-oqlos",
        }
    if normalized == "rtc":
        from oqlos.hardware.transport.manage_ops import run_manage_verb
        result = await run_manage_verb("rtc-status")
        return {
            "ok": _ok_from_result(result),
            "peripheral_id": normalized,
            "command": "status",
            "result": result,
            "transport": "direct-oqlos",
        }
    if normalized == "barcode-scanner":
        from oqlos.api import hardware as hw
        identify = await hw.hardware_identify(scan="never")
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
        from oqlos.api import hardware as hw
        identify = await hw.hardware_identify(scan="never")
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


@sub_router.post("/diagnostic-command")
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


@sub_router.get("/scanner/status")
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


@sub_router.get("/scanner/last")
async def hardware_scanner_last_v3() -> dict[str, Any]:
    return {"success": True, "data": _scanner_last, "source": "oqlos-local"}


@sub_router.post("/scanner/ingest")
async def hardware_scanner_ingest_v3(payload: ScannerIngestRequest) -> dict[str, Any]:
    global _scanner_last
    _scanner_last = {
        "code": payload.code,
        "source": payload.source,
        "symbology": payload.symbology,
        "metadata": payload.metadata or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return {"success": True, "data": _scanner_last, "source": "oqlos-local"}
