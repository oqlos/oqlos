"""Generic peripheral diagnostic-command routing for manage_ops."""

from __future__ import annotations

from typing import Any

from oqlos.hardware.client.tic249_command_mapping import map_tic249_command
from oqlos.hardware.client.tic249_error_messages import extract_position
from oqlos.hardware.client.tic249_extended import MOTOR_TIC249_EXTENDED_COMMANDS
from oqlos.hardware.client.tic249_motion_params import normalize_motion_params
from oqlos.hardware.client.tic249_rig_direction import RIG_LEFT_ALIASES


def _success_from_result(result: Any) -> bool:
    if isinstance(result, dict):
        if "success" in result:
            return bool(result["success"])
        if "ok" in result:
            return bool(result["ok"])
        return not bool(result.get("error"))
    return bool(result)


async def run_modbus_io_valve(hw: Any, command: str, params: dict[str, Any]) -> dict[str, Any]:
    valve_id = str(params.get("valve_id") or "").strip()
    if not valve_id:
        raise ValueError("modbus-io diagnostic command requires 'valve_id'")
    value = command == "valve_on" if command != "set_valve" else bool(params.get("value", False))
    result = await hw.set_valve(valve_id, value)
    if isinstance(result, dict):
        success = bool(result.get("success", result.get("ok", False)))
    else:
        success = bool(result)
    return {"success": success, "ok": success, "valve_id": valve_id, "value": value, "result": result}


async def run_pump_diagnostic(command: str, params: dict[str, Any]) -> dict[str, Any]:
    """Map connect-scenario pump_off/pump_set to the motor plugin set_speed path."""
    from oqlos.api.hardware_gateway import get_hardware_gateway

    power = 0.0 if command == "pump_off" else float(params.get("power_pct", 0))
    result = await get_hardware_gateway().set_pump(power)
    success = _success_from_result(result)
    return {
        "success": success,
        "ok": success,
        "power_pct": power,
        "result": result,
    }


async def _resolve_move_relative_params(params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    from oqlos.api import plugins as pl

    status = await pl.execute_plugin_command("motor-tic249", {"command": "status", "params": {}})
    current = extract_position(status)
    offset = params.get("offset")
    if offset is None:
        steps = abs(int(params.get("steps", 0)))
        direction = str(params.get("direction", "right")).lower()
        offset = -steps if direction in RIG_LEFT_ALIASES else steps
    raw_params = {**params, "offset": int(offset), "position": current + int(offset)}
    raw_params.pop("direction", None)
    raw_params.pop("steps", None)
    mapped = normalize_motion_params(raw_params)
    mapped["relative_from"] = current
    mapped["offset"] = int(offset)
    return "move", mapped


async def run_motor_tic249_extended(command: str, params: dict[str, Any]) -> dict[str, Any]:
    """Run Tic249 UI commands locally (same names as connect-scenario proxy)."""
    from oqlos.api import plugins as pl

    plugin_command, mapped_params = map_tic249_command(command, params)
    if command == "move_relative":
        plugin_command, mapped_params = await _resolve_move_relative_params(params)
    result = await pl.execute_plugin_command(
        "motor-tic249",
        {"command": plugin_command, "params": mapped_params},
    )
    success = _success_from_result(result)
    return {
        "success": success,
        "ok": success,
        "command": command,
        "plugin_command": plugin_command,
        "result": result,
    }


_TIC249_DISABLE_COMMANDS = frozenset({"motor_disable", "deenergize", "disable", "standby"})
_TIC249_STOP_COMMANDS = frozenset({"stop", "lung_stop", "stop_lung", "emergency_stop"})


def _extract_diagnostic_ids(a: dict[str, Any]) -> tuple[str, str]:
    plugin_id = str(a.get("peripheral_id") or a.get("plugin_id") or "").strip()
    if not plugin_id:
        raise ValueError("diagnostic-command requires 'peripheral_id'")
    command = str(a.get("command") or "").strip()
    return plugin_id, command


def _extract_params(a: dict[str, Any]) -> dict[str, Any]:
    args = a.get("args")
    if isinstance(args, dict):
        return args
    params = a.get("params")
    return params if isinstance(params, dict) else {}


async def _route_tic249_lung_command(command: str, hw: Any) -> dict[str, Any] | None:
    if command in _TIC249_DISABLE_COMMANDS:
        return await hw.disable_lung()
    if command in _TIC249_STOP_COMMANDS:
        return await hw.stop_lung()
    return None


async def _route_diagnostic_command(plugin_id: str, command: str, params: dict[str, Any], hw: Any, pl: Any) -> dict[str, Any]:
    if plugin_id == "modbus-io" and command in {"valve_on", "valve_off", "set_valve"}:
        return await run_modbus_io_valve(hw, command, params)
    if plugin_id == "motor-dri0050" and command in {"pump_off", "pump_set"}:
        return await run_pump_diagnostic(command, params)
    if plugin_id == "motor-tic249" and command in MOTOR_TIC249_EXTENDED_COMMANDS:
        return await run_motor_tic249_extended(command, params)
    return await pl.execute_plugin_command(plugin_id, {"command": command, "params": params})


async def run_diagnostic_command(a: dict[str, Any]) -> dict[str, Any]:
    """Generic peripheral command — mirrors connect-scenario's proxy_diagnostic_command.

    Routes ``{peripheral_id, command, args}`` to the plugin's execute endpoint, so a
    CQRS hardware command from connect-scenario can flow over MQTT to the remote Pi
    unchanged. ``peripheral_id`` is used directly as the plugin id (the caller has
    already canonicalized it via ``normalize_peripheral_id``).
    """
    from oqlos.api import hardware as hw
    from oqlos.api import plugins as pl

    plugin_id, command = _extract_diagnostic_ids(a)
    if plugin_id == "motor-tic249":
        lung_result = await _route_tic249_lung_command(command, hw)
        if lung_result is not None:
            return lung_result
    params = _extract_params(a)
    return await _route_diagnostic_command(plugin_id, command, params, hw, pl)
