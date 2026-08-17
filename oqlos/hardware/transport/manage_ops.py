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

from oqlos.hardware.transport.manage_ops_diagnostic import run_diagnostic_command
from oqlos.hardware.transport.manage_ops_usb import pi_diagnostics, usb_list, usb_reset

# Verbs that take no arguments map straight to a zero-arg handler.
_NULLARY = {
    "health",
    "diagnose",
    "stack-snapshot",
    "waveshare-diagnose",
    "wizard-plan",
    "hui-actions",
    "hui-readiness",
    "hui-shutdown",
    "hui-al-start",
    "hui-al-stop",
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
    from oqlos.api import hardware_modbus_routes as modbus_hw

    nullary_map: dict[str, Callable[[], Awaitable[Any]]] = {
        "health": hw.hardware_health,
        "diagnose": hw.hardware_diagnose,
        "stack-snapshot": hw.hardware_stack_snapshot,
        "waveshare-diagnose": modbus_hw.hardware_modbus_waveshare_diagnose,
        "io-verify": modbus_hw.hardware_modbus_io_verify,
        "io-repair": modbus_hw.hardware_modbus_io_repair,
        "wizard-plan": modbus_hw.hardware_modbus_wizard_plan,
        "hui-actions": hw.hui_actions,
        "hui-readiness": hw.hui_readiness,
        "hui-shutdown": hw.hui_shutdown,
        "hui-al-start": hw.hui_al_start,
        "hui-al-stop": hw.hui_al_stop,
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

    parametric_map: dict[str, Callable[[dict[str, Any]], Awaitable[Any]]] = {
        "identify": lambda a: hw.hardware_identify(scan=a.get("scan", "never")),
        "diagnosis": lambda a: hw.hardware_diagnosis_route(scan=a.get("scan", "never")),
        "recover": lambda a: hw.hardware_recover_route(scope=a.get("scope", "safe")),
        "wizard-probe": lambda a: modbus_hw.hardware_modbus_wizard_probe_isolated(
            serial_port=a.get("serial_port", ""),
            baudrates=a.get("baudrates"),
            parities=a.get("parities"),
            device_ids=a.get("device_ids"),
            module_role=a.get("module_role", ""),
        ),
        "wizard-program": lambda a: modbus_hw.hardware_modbus_wizard_program_isolated(
            serial_port=a.get("serial_port", ""),
            current_device_id=int(a.get("current_device_id", 1)),
            new_device_id=int(a.get("new_device_id", 1)),
            new_baudrate=int(a.get("new_baudrate", 4800)),
            new_parity=a.get("new_parity", "N"),
            confirm_isolated=bool(a.get("confirm_isolated", False)),
        ),
        "valve": lambda a: hw.set_valve(str(a["valve_id"]), bool(a.get("value", False))),
        "pump": lambda a: hw.set_pump(float(a.get("power_pct", 0.0))),
        "sensor": lambda a: hw.read_sensor(str(a["sensor_id"])),
        "lung": lambda a: hw.set_lung(
            steps=int(a.get("steps", 500)),
            speed=int(a["speed"]) if a.get("speed") is not None else hw.TIC249_DEFAULT_TARGET_VELOCITY,
            cycles=int(a.get("cycles", 5)),
            pause=float(a.get("pause", 0.5)),
        ),
        "hui-hold-start": lambda a: hw.hui_hold_start(str(a["key"])),
        "hui-hold-stop": lambda a: hw.hui_hold_stop(str(a.get("key", ""))),
        "artificial-lung-command": lambda a: hw.artificial_lung_command(a.get("payload", {})),
        "rtc-command": lambda a: hw.rtc_command(a.get("payload", {})),
        "diagnostic-command": run_diagnostic_command,
        "usb-list": usb_list,
        "list-usb": usb_list,
        "pi-diagnostics": pi_diagnostics,
        "usb-reset": usb_reset,
    }
    handler = parametric_map.get(key)
    if handler is not None:
        return handler

    raise ValueError(f"unknown manage verb: {verb!r}")


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
            "hui-hold-start",
            "hui-hold-stop",
            "artificial-lung-command",
            "rtc-command",
            "diagnostic-command",
            "usb-list",
            "pi-diagnostics",
            "usb-reset",
        }
    )
