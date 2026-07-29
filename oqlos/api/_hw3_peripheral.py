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
from oqlos.errors import OqlosError
from oqlos.hardware.client.errors import diagnostic_issue_for_peripheral
from oqlos.hardware.client.resolvers import extract_command_failure

sub_router = APIRouter()

_scanner_last: dict[str, Any] | None = None

_INVALID_DIAGNOSTIC_MARKERS = (
    "unsupported diagnostic command",
    "unsupported command",
    "requires '",
    "requires \"",
    "invalid ",
    "missing ",
    "unknown command",
    "not allowed",
)


def _diagnostic_failure_is_invalid(message: str) -> bool:
    lowered = str(message or "").strip().lower()
    return any(marker in lowered for marker in _INVALID_DIAGNOSTIC_MARKERS)


def _diagnostic_error_context(peripheral_id: str, command: str) -> dict[str, str]:
    normalized = normalize_peripheral_id(peripheral_id)[:128] or "unknown"
    safe_command = str(command or "unknown").strip()[:128] or "unknown"
    return {
        "architecture": "SOA",
        "layer": "firmware",
        "component": "hardware-diagnostics",
        "stage": "diagnostic.execute",
        "problem_source": "upstream",
        "operation_id": "hardware.diagnostic-command",
        "peripheral_id": normalized,
        "command": safe_command,
        "upstream_target": f"hardware-peripheral://{normalized}",
    }


def _raise_diagnostic_command_failure(
    peripheral_id: str,
    command: str,
    result: dict[str, Any],
    *,
    cause: Exception | None = None,
) -> None:
    message = extract_command_failure(result) or str(
        result.get("error")
        or result.get("message")
        or f"Diagnostic command '{command}' failed for '{peripheral_id}'"
    )
    invalid = _diagnostic_failure_is_invalid(message)
    if invalid:
        error = OqlosError(
            code="api_diagnostic_command_invalid",
            status_code=400,
            detail=_diagnostic_error_context(peripheral_id, command),
        )
    else:
        error = OqlosError(
            code=diagnostic_issue_for_peripheral(peripheral_id),
            status_code=503,
            detail=_diagnostic_error_context(peripheral_id, command),
        )
    if cause is not None:
        raise error from cause
    raise error


def _raise_peripheral_status_failure(
    peripheral_id: str,
    result: dict[str, Any],
    *,
    cause: Exception | None = None,
) -> None:
    error = OqlosError(
        code=diagnostic_issue_for_peripheral(peripheral_id),
        status_code=503,
        detail=_diagnostic_error_context(peripheral_id, "status"),
    )
    if cause is not None:
        raise error from cause
    raise error


@sub_router.get("/peripheral-status/{peripheral_id}")
async def hardware_peripheral_status_v3(peripheral_id: str) -> dict[str, Any]:
    normalized = normalize_peripheral_id(peripheral_id)
    if normalized == "artificial-lung":
        from oqlos.hardware.transport.manage_ops import run_manage_verb
        result = await run_manage_verb("artificial-lung-status")
        response = {
            "ok": _ok_from_result(result),
            "peripheral_id": normalized,
            "command": "status",
            "result": result,
            "transport": "direct-oqlos",
        }
        if response["ok"]:
            return response
        _raise_peripheral_status_failure("motor-tic249", response)
    if normalized == "rtc":
        from oqlos.hardware.transport.manage_ops import run_manage_verb
        result = await run_manage_verb("rtc-status")
        response = {
            "ok": _ok_from_result(result),
            "peripheral_id": normalized,
            "command": "status",
            "result": result,
            "transport": "direct-oqlos",
        }
        if response["ok"]:
            return response
        _raise_peripheral_status_failure(normalized, response)
    if normalized == "barcode-scanner":
        from oqlos.api import hardware as hw
        identify = await hw.hardware_identify(scan="never")
        adapter = _find_adapter(identify, normalized)
        response = {
            "ok": bool(adapter and adapter.get("status") == "ok"),
            "peripheral_id": normalized,
            "command": "scanner_status",
            "result": adapter or {},
            "status": adapter.get("status") if adapter else "unknown",
            "transport": "direct-oqlos",
        }
        if response["ok"]:
            return response
        _raise_peripheral_status_failure(normalized, response)
    try:
        result = await _run_diagnostic(normalized, "status", {})
        if _ok_from_result(result):
            return result
        _raise_peripheral_status_failure(normalized, result)
    except OqlosError:
        raise
    except Exception as exc:
        from oqlos.api import hardware as hw
        identify = await hw.hardware_identify(scan="never")
        adapter = _find_adapter(identify, normalized)
        fallback = {
            "ok": bool(adapter and adapter.get("status") == "ok"),
            "peripheral_id": normalized,
            "command": "status",
            "result": adapter or {},
            "status": adapter.get("status") if adapter else "unknown",
            "error": str(exc),
            "transport": "direct-oqlos",
        }
        if fallback["ok"]:
            return fallback
        _raise_peripheral_status_failure(normalized, fallback, cause=exc)


@sub_router.post("/diagnostic-command")
async def hardware_diagnostic_command_v3(req: DiagnosticCommandRequest) -> dict[str, Any]:
    try:
        result = await _run_diagnostic(req.peripheral_id, req.command, req.args)
        failure = extract_command_failure(result)
        if failure is None and _ok_from_result(result):
            return result
        _raise_diagnostic_command_failure(
            normalize_peripheral_id(req.peripheral_id), req.command, result
        )
    except HTTPException:
        raise
    except OqlosError:
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
        await publish_hardware_command_event(
            {"payload": payload}, result, context={"source": "diagnostic-command"}
        )
        _raise_diagnostic_command_failure(
            payload["peripheral_id"], req.command, result, cause=exc
        )


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
