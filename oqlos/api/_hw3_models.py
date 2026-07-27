"""Shared models, constants, and helpers for the /api/v3/hardware router."""
from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel

from oqlos.api.hardware_events import publish_hardware_command_event
from oqlos.hardware.transport.manage_ops import run_manage_verb

_PERIPHERAL_ALIASES: dict[str, str] = {
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


async def _hardware_v1_call(name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    from oqlos.api import hardware as hw
    return await getattr(hw, name)(*args, **kwargs)
