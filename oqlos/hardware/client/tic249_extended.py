from __future__ import annotations

from typing import Any

from oqlos.hardware.client.errors import HardwareProxyError, is_oqlos_unavailable, oqlos_error_detail
from oqlos.hardware.client.proxy import OqlosHardwareProxy
from oqlos.hardware.client.tic249_command_mapping import map_tic249_command
from oqlos.hardware.client.tic249_error_messages import (
    command_failure,
    extract_position,
    normalize_target_state,
    plugin_unavailable_error,
)
from oqlos.hardware.client.tic249_motion_params import build_reciprocate_params, normalize_motion_params
from oqlos.hardware.client.tic249_rig_direction import RIG_LEFT_ALIASES
from oqlos.hardware.client.tic249_sidecar_client import (
    attempt_disable_deenergize,
    attempt_reciprocate_via_sidecar,
    direct_sidecar_deenergize,
    disable_success_response,
    sidecar_reciprocate_preferred,
    sidecar_reports_deenergized,
)

MOTOR_TIC249_EXTENDED_COMMANDS = {
    "deenergize",
    "disable",
    "energize",
    "emergency_stop",
    "go_home",
    "home",
    "home_forward",
    "home_reverse",
    "limits",
    "lung_start",
    "lung_stop",
    "motor_disable",
    "motor_enable",
    "move",
    "move_relative",
    "position",
    "reciprocating_motion",
    "standby",
    "status",
    "stop",
    "stroke_sequence",
    "tic249_reciprocate",
    "tic249_stroke_sequence",
    "tic249_cycle",
    "tic249_inhale",
    "tic249_forward",
    "tic249_exhale",
    "tic249_backward",
    "tic249_stop",
    "reciprocate_v2",
}

_PLUGIN_PATH = "/api/v1/plugins/motor-tic249/execute"
_DISABLE_COMMANDS = frozenset({"motor_disable", "deenergize", "disable", "standby"})
_RECIPROCATE_PLUGIN_COMMAND = "reciprocate"

# Backward-compatible aliases for tests and internal callers.
_build_reciprocate_params = build_reciprocate_params
_direct_sidecar_deenergize = direct_sidecar_deenergize
_sidecar_reports_deenergized = sidecar_reports_deenergized
_attempt_reciprocate_via_sidecar = attempt_reciprocate_via_sidecar


def _plugin_payload(command: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"command": command, "params": params or {}}


async def _execute(proxy: OqlosHardwareProxy, command: str, params: dict[str, Any] | None = None) -> Any:
    return await proxy._proxy_oqlos_request("POST", _PLUGIN_PATH, payload=_plugin_payload(command, params))


async def _handle_move_relative_command(
    hardware_proxy: OqlosHardwareProxy,
    command_args: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Resolve move_relative into absolute position params; return (plugin_command, params)."""
    status = await _execute(hardware_proxy, "status", {})
    current = extract_position(status)
    offset = command_args.get("offset")
    if offset is None:
        steps = abs(int(command_args.get("steps", 0)))
        direction = str(command_args.get("direction", "right")).lower()
        offset = -steps if direction in RIG_LEFT_ALIASES else steps
    raw_params = {**command_args, "offset": int(offset), "position": current + int(offset)}
    raw_params.pop("direction", None)
    raw_params.pop("steps", None)
    params = normalize_motion_params(raw_params)
    params["relative_from"] = current
    params["offset"] = int(offset)
    return "move", params


async def _try_disable_fallback(
    hardware_proxy: OqlosHardwareProxy,
    command: str,
) -> dict[str, Any] | None:
    if command not in _DISABLE_COMMANDS:
        return None
    fallback_result, fallback_name = await attempt_disable_deenergize(hardware_proxy, command)
    if fallback_result is not None and fallback_name is not None:
        return disable_success_response(command, fallback_result, fallback_name)
    return None


async def _try_sidecar_reciprocate(
    command: str,
    plugin_command: str,
    params: dict[str, Any],
) -> dict[str, Any] | None:
    if plugin_command != _RECIPROCATE_PLUGIN_COMMAND or not sidecar_reciprocate_preferred():
        return None
    sidecar_result, sidecar_base = await attempt_reciprocate_via_sidecar(params)
    if sidecar_result is None or sidecar_base is None:
        return None
    return {
        "ok": True,
        "peripheral_id": "motor-tic249",
        "command": command,
        "target": {"method": "POST", "path": f"{sidecar_base}/api/reciprocate", "params": params},
        "result": sidecar_result,
        "note": (
            "Reciprocate via Tic249 sidecar (physical limit switches; "
            "set TIC249_RECIPROCATE_VIA_SIDECAR=0 to use OqlOS plugin only)"
        ),
    }


async def _handle_hardware_proxy_error(
    hardware_proxy: OqlosHardwareProxy,
    command: str,
    plugin_command: str,
    params: dict[str, Any],
    exc: HardwareProxyError,
) -> dict[str, Any] | None:
    if command in _DISABLE_COMMANDS and plugin_unavailable_error(exc):
        fallback_result, fallback_name = await attempt_disable_deenergize(hardware_proxy, command)
        if fallback_result is not None and fallback_name is not None:
            return disable_success_response(command, fallback_result, fallback_name)
        message, detail = oqlos_error_detail(exc)
        return {
            "ok": False,
            "peripheral_id": "motor-tic249",
            "command": command,
            "target": {"method": "POST", "path": _PLUGIN_PATH, "params": _plugin_payload(plugin_command, params)},
            "error": (
                "Cannot de-energize Tic T249: plugin not active and sidecar/lung fallbacks failed. "
                f"{message}"
            ),
            "hint": (
                "Ensure hw-tic249 is running (e.g. port 8205) and set OQLOS_LUNG_MOTOR_URL / TIC249_URL "
                "to a reachable base URL from connect-scenario-backend"
            ),
            "result": {"success": False, "error": message, "detail": detail},
        }
    if command == "status" and plugin_unavailable_error(exc):
        return {
            "ok": True,
            "optional": True,
            "peripheral_id": "motor-tic249",
            "command": command,
            "target": {"method": "POST", "path": _PLUGIN_PATH, "params": _plugin_payload(plugin_command, params)},
            "note": "motor-tic249 plugin disabled (bench Modbus-only); status step treated as skipped",
            "result": {"status": "disabled", "success": True, "idempotent_success": True},
        }
    if not is_oqlos_unavailable(exc):
        return None
    message, detail = oqlos_error_detail(exc)
    return {
        "ok": False,
        "peripheral_id": "motor-tic249",
        "command": command,
        "target": {"method": "POST", "path": _PLUGIN_PATH, "params": _plugin_payload(plugin_command, params)},
        "error": message,
        "result": {"success": False, "error": message, "detail": detail},
    }


async def run_extended_motor_tic249_command(
    hardware_proxy: OqlosHardwareProxy,
    command: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    command_args = args or {}
    plugin_command, params = map_tic249_command(command, command_args)

    if command == "move_relative":
        plugin_command, params = await _handle_move_relative_command(hardware_proxy, command_args)

    disable_response = await _try_disable_fallback(hardware_proxy, command)
    if disable_response is not None:
        return disable_response

    sidecar_response = await _try_sidecar_reciprocate(command, plugin_command, params)
    if sidecar_response is not None:
        return sidecar_response

    try:
        result = await _execute(hardware_proxy, plugin_command, params)
    except HardwareProxyError as exc:
        error_response = await _handle_hardware_proxy_error(hardware_proxy, command, plugin_command, params, exc)
        if error_response is not None:
            return error_response
        raise

    result = normalize_target_state(command, result)
    failure = command_failure(result)
    if failure:
        disable_response = await _try_disable_fallback(hardware_proxy, command)
        if disable_response is not None:
            return disable_response
    return {
        "ok": failure is None,
        "peripheral_id": "motor-tic249",
        "command": command,
        "target": {"method": "POST", "path": _PLUGIN_PATH, "params": _plugin_payload(plugin_command, params)},
        **({"error": failure} if failure else {}),
        "result": result,
    }
