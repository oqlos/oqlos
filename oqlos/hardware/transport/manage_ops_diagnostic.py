"""Generic peripheral diagnostic-command routing for manage_ops."""

from __future__ import annotations

from typing import Any


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


async def run_diagnostic_command(a: dict[str, Any]) -> dict[str, Any]:
    """Generic peripheral command — mirrors connect-scenario's proxy_diagnostic_command.

    Routes ``{peripheral_id, command, args}`` to the plugin's execute endpoint, so a
    CQRS hardware command from connect-scenario can flow over MQTT to the remote Pi
    unchanged. ``peripheral_id`` is used directly as the plugin id (the caller has
    already canonicalized it via ``normalize_peripheral_id``).
    """
    from oqlos.api import hardware as hw
    from oqlos.api import plugins as pl

    plugin_id = str(a.get("peripheral_id") or a.get("plugin_id") or "").strip()
    if not plugin_id:
        raise ValueError("diagnostic-command requires 'peripheral_id'")
    command = str(a.get("command") or "").strip()
    if plugin_id == "motor-tic249":
        if command in {"motor_disable", "deenergize", "disable", "standby"}:
            return await hw.disable_lung()
        if command in {"stop", "lung_stop", "stop_lung", "emergency_stop"}:
            return await hw.stop_lung()
    params: dict[str, Any] = (
        a.get("args")
        if isinstance(a.get("args"), dict)
        else (a.get("params") if isinstance(a.get("params"), dict) else {})
    )
    if plugin_id == "modbus-io" and command in {"valve_on", "valve_off", "set_valve"}:
        return await run_modbus_io_valve(hw, command, params)
    return await pl.execute_plugin_command(plugin_id, {"command": command, "params": params})
