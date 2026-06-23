"""
oqlos.hardware.transport.manage_ops — management/diagnostic verbs over MQTT.

The OQL command/script channel covers actuation (SET/GET). This module covers the
read-only and lifecycle hardware operations that are not expressible as OQL —
identify, health, diagnose, recover, stack snapshot, the Modbus wizard, and direct
peripheral pokes — so the application node can drive the *entire* hardware surface
of a remote Pi purely over MQTT, with the Pi's HTTP :8202 kept loopback-only.

Each verb dispatches to the existing oqlos.api.hardware route handlers (imported
lazily to avoid an import cycle with the transport package). Those handlers use the
process-global gateway installed via ``set_hardware_gateway`` — the same singleton
the MQTT agent shares — so no second gateway is constructed.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

# Verbs that take no arguments map straight to a zero-arg handler.
_NULLARY = {
    "health",
    "diagnose",
    "stack-snapshot",
    "waveshare-diagnose",
    "wizard-plan",
    "lung-stop",
    "lung-disable",
    "artificial-lung-status",
    "rtc-status",
    "modbus-adc-raw",
    "temperature",
}


async def run_manage_verb(verb: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a management verb and return a JSON-serializable result dict.

    Raises ``ValueError`` for an unknown verb; all other handler exceptions
    propagate to the caller (the agent wraps them into an ``ok=False`` response).
    """
    args = args or {}
    handler = _resolve(verb)
    result = await handler(args)
    if isinstance(result, dict):
        return result
    return {"result": result}


def _resolve(verb: str) -> Callable[[dict[str, Any]], Awaitable[Any]]:
    key = (verb or "").strip().lower()

    # Import lazily — oqlos.api.hardware pulls in the FastAPI router.
    from oqlos.api import hardware as hw

    nullary_map: dict[str, Callable[[], Awaitable[Any]]] = {
        "health": hw.hardware_health,
        "diagnose": hw.hardware_diagnose,
        "stack-snapshot": hw.hardware_stack_snapshot,
        "waveshare-diagnose": hw.hardware_modbus_waveshare_diagnose,
        "wizard-plan": hw.hardware_modbus_wizard_plan,
        "lung-stop": hw.stop_lung,
        "lung-disable": hw.disable_lung,
        "artificial-lung-status": hw.artificial_lung_status,
        "rtc-status": hw.rtc_status,
        "modbus-adc-raw": hw.read_modbus_adc_raw,
        "temperature": hw.hardware_temperature,
    }
    if key in nullary_map:
        fn = nullary_map[key]
        return lambda _args: fn()

    if key == "identify":
        return lambda a: hw.hardware_identify(scan=a.get("scan", "never"))
    if key == "diagnosis":
        return lambda a: hw.hardware_diagnosis_route(scan=a.get("scan", "never"))
    if key == "recover":
        return lambda a: hw.hardware_recover_route(scope=a.get("scope", "safe"))
    if key == "wizard-probe":
        return lambda a: hw.hardware_modbus_wizard_probe_isolated(
            serial_port=a.get("serial_port", ""),
            baudrates=a.get("baudrates"),
            parities=a.get("parities"),
            device_ids=a.get("device_ids"),
            module_role=a.get("module_role", ""),
        )
    if key == "wizard-program":
        return lambda a: hw.hardware_modbus_wizard_program_isolated(
            serial_port=a.get("serial_port", ""),
            current_device_id=int(a.get("current_device_id", 1)),
            new_device_id=int(a.get("new_device_id", 1)),
            new_baudrate=int(a.get("new_baudrate", 9600)),
            new_parity=a.get("new_parity", "N"),
            confirm_isolated=bool(a.get("confirm_isolated", False)),
        )
    if key == "valve":
        return lambda a: hw.set_valve(str(a["valve_id"]), bool(a.get("value", False)))
    if key == "pump":
        return lambda a: hw.set_pump(float(a.get("power_pct", 0.0)))
    if key == "sensor":
        return lambda a: hw.read_sensor(str(a["sensor_id"]))
    if key == "lung":
        return lambda a: hw.set_lung(
            steps=int(a.get("steps", 500)),
            speed=int(a["speed"]) if a.get("speed") is not None else hw.TIC249_DEFAULT_TARGET_VELOCITY,
            cycles=int(a.get("cycles", 5)),
            pause=float(a.get("pause", 0.5)),
        )
    if key == "artificial-lung-command":
        return lambda a: hw.artificial_lung_command(a.get("payload", {}))
    if key == "rtc-command":
        return lambda a: hw.rtc_command(a.get("payload", {}))
    if key == "diagnostic-command":
        return _run_diagnostic_command

    raise ValueError(f"unknown manage verb: {verb!r}")


async def _run_diagnostic_command(a: dict[str, Any]) -> dict[str, Any]:
    """Generic peripheral command — mirrors connect-scenario's proxy_diagnostic_command.

    Routes ``{peripheral_id, command, args}`` to the plugin's execute endpoint, so a
    CQRS hardware command from connect-scenario can flow over MQTT to the remote Pi
    unchanged. ``peripheral_id`` is used directly as the plugin id (the caller has
    already canonicalized it via ``normalize_peripheral_id``).
    """
    from oqlos.api import plugins as pl

    plugin_id = str(a.get("peripheral_id") or a.get("plugin_id") or "").strip()
    if not plugin_id:
        raise ValueError("diagnostic-command requires 'peripheral_id'")
    params = a.get("args")
    if not isinstance(params, dict):
        params = a.get("params") if isinstance(a.get("params"), dict) else {}
    return await pl.execute_plugin_command(plugin_id, {"command": a.get("command"), "params": params})


def list_manage_verbs() -> list[str]:
    """Return the supported verb names (for discovery/tests)."""
    return sorted(
        _NULLARY
        | {
            "identify",
            "diagnosis",
            "recover",
            "wizard-probe",
            "wizard-program",
            "valve",
            "pump",
            "sensor",
            "lung",
            "artificial-lung-command",
            "rtc-command",
            "diagnostic-command",
        }
    )
