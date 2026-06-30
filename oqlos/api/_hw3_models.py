"""Shared models, constants, and helpers for the /api/v3/hardware router."""
from __future__ import annotations

import asyncio
from typing import Any, Literal

from pydantic import BaseModel

from oqlos.api.hardware_events import publish_hardware_command_event
from oqlos.api.hardware_mapping_contract import MappingContractError
from oqlos.api.hardware_mapping_store import normalize_mapping
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


async def _hardware_v1_call(name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    from oqlos.api import hardware as hw
    return await getattr(hw, name)(*args, **kwargs)
