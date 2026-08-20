"""Map peripheral diagnostic commands to OqlOS REST targets."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from oqlos.hardware.client.adc import adc_sensor_alias
from oqlos.hardware.client.constants import (
    ARTIFICIAL_LUNG_IDS,
    MODBUS_ALLOWED_VALVE_IDS,
    TIC249_DEFAULT_TARGET_VELOCITY,
)
from oqlos.hardware.client.errors import HardwareProxyError
from oqlos.hardware.valve_controller import (
    DEFAULT_VALVE_CONTROLLER_PREFERENCE,
    MODBUS_VALVE_CONTROLLER,
)


def normalize_modbus_valve_id(raw: Any, peripheral: str = MODBUS_VALVE_CONTROLLER) -> str:
    valve_id = str(raw or "valve-1").strip().lower().replace("_", "-")
    if valve_id not in MODBUS_ALLOWED_VALVE_IDS:
        raise HardwareProxyError(
            400,
            (
                f"Unsupported valve_id '{valve_id}' for peripheral '{peripheral}'. "
                "Expected valve-1..valve-14, valve-nc, valve-sc, or valve-wc"
            ),
        )
    return valve_id


def resolve_valve_target(
    peripheral: str, command: str, args: dict[str, Any]
) -> tuple[str, str, dict[str, Any] | None]:
    """Route a valve command to any configured valve output module.

    The REST target is controller-agnostic: ``/api/v1/hardware/valve/{id}`` runs
    through the gateway's valve failover, so this resolver must not be pinned to
    ``modbus-io`` — a stand on ``io-m5-4in8out`` sends the same command.
    """
    valve_id = normalize_modbus_valve_id(args.get("valve_id"), peripheral)
    if command == "valve_on":
        return "POST", f"/api/v1/hardware/valve/{valve_id}", {"value": True}
    if command == "valve_off":
        return "POST", f"/api/v1/hardware/valve/{valve_id}", {"value": False}
    if command == "set_valve":
        return (
            "POST",
            f"/api/v1/hardware/valve/{valve_id}",
            {"value": bool(args.get("value", False))},
        )
    raise HardwareProxyError(
        400, f"Unsupported diagnostic command '{command}' for peripheral '{peripheral}'"
    )


def resolve_modbus_target(command: str, args: dict[str, Any]) -> tuple[str, str, dict[str, Any] | None]:
    return resolve_valve_target(MODBUS_VALVE_CONTROLLER, command, args)


def resolve_pump_target(command: str, args: dict[str, Any]) -> tuple[str, str, dict[str, Any] | None]:
    if command == "pump_set":
        return "POST", "/api/v1/hardware/pump", {"power_pct": float(args.get("power_pct", 20))}
    if command == "pump_off":
        return "POST", "/api/v1/hardware/pump", {"power_pct": 0.0}
    raise HardwareProxyError(400, f"Unsupported diagnostic command '{command}' for peripheral 'motor-dri0050'")


def resolve_artificial_lung_target(command: str, args: dict[str, Any]) -> tuple[str, str, dict[str, Any] | None]:
    return "POST", "/api/v1/hardware/artificial-lung/command", {"command": command, "args": args}


def resolve_lung_target(command: str, args: dict[str, Any]) -> tuple[str, str, dict[str, Any] | None]:
    if command == "lung_start":
        return "POST", "/api/v1/hardware/lung", {
            "steps": int(args.get("steps", 500)),
            "speed": int(args.get("speed", TIC249_DEFAULT_TARGET_VELOCITY)),
            "cycles": int(args.get("cycles", 3)),
            "pause": float(args.get("pause", 0.5)),
        }
    if command == "lung_stop":
        return "POST", "/api/v1/hardware/lung/stop", None
    if command == "motor_disable":
        return "POST", "/api/v1/hardware/lung/disable", None
    raise HardwareProxyError(400, f"Unsupported diagnostic command '{command}' for peripheral 'motor-tic249'")


def resolve_modbus_adc_target(command: str, args: dict[str, Any]) -> tuple[str, str, dict[str, Any] | None]:
    if command == "read_sensor":
        _public_sensor_id, oqlos_sensor_id = adc_sensor_alias(args.get("sensor_id") or "v1")
        return "GET", f"/api/v1/hardware/sensor/{oqlos_sensor_id}", None
    if command == "read_all":
        return "POST", "/api/v1/plugins/modbus-adc/execute", None
    raise HardwareProxyError(400, f"Unsupported diagnostic command '{command}' for peripheral 'modbus-adc'")


def resolve_rtc_target(command: str, args: dict[str, Any]) -> tuple[str, str, dict[str, Any] | None]:
    return "POST", "/api/v1/hardware/rtc/command", {"command": command, "args": args}


def resolve_diagnostic_target(peripheral: str, command: str, args: dict[str, Any]) -> tuple[str, str, dict[str, Any] | None]:
    # A common, read-only diagnostic that never needs a device-specific
    # command mapping and never actuates the peripheral.
    if command == "status":
        return (
            "GET",
            f"/api/v3/hardware/peripheral-status/{quote(peripheral, safe='')}",
            None,
        )
    if peripheral in ARTIFICIAL_LUNG_IDS:
        return resolve_artificial_lung_target(command, args)
    if peripheral in DEFAULT_VALVE_CONTROLLER_PREFERENCE:
        return resolve_valve_target(peripheral, command, args)
    resolvers = {
        "motor-dri0050": resolve_pump_target,
        "motor-tic249": resolve_lung_target,
        "modbus-adc": resolve_modbus_adc_target,
        "piadc": resolve_modbus_adc_target,
        "rtc": resolve_rtc_target,
    }
    resolver = resolvers.get(peripheral)
    if not resolver:
        raise HardwareProxyError(400, f"Unsupported diagnostic command '{command}' for peripheral '{peripheral}'")
    return resolver(command, args)


def _coalesce_error_message(*candidates: Any) -> str | None:
    for candidate in candidates:
        if candidate is None:
            continue
        text = str(candidate).strip()
        if text:
            return text
    return None


def extract_command_failure(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None
    if result.get("success") is False:
        return _coalesce_error_message(result.get("error"), result.get("message"), result.get("detail")) or "Command failed"
    nested_ok = result.get("ok")
    if nested_ok is False:
        return _coalesce_error_message(result.get("error"), result.get("message"), result.get("detail")) or "Command failed (ok=false)"
    if isinstance(nested_ok, dict) and nested_ok.get("success") is False:
        nested_data = nested_ok.get("data") if isinstance(nested_ok.get("data"), dict) else {}
        return (
            _coalesce_error_message(
                nested_ok.get("error"),
                nested_ok.get("message"),
                nested_ok.get("detail"),
                nested_data.get("error"),
                nested_data.get("message"),
                result.get("error"),
                result.get("message"),
                result.get("detail"),
            )
            or "Command failed (motor driver returned success=false with no error detail)"
        )
    nested_data = result.get("data")
    if isinstance(nested_data, dict) and nested_data.get("success") is False:
        return (
            _coalesce_error_message(
                nested_data.get("error"),
                nested_data.get("message"),
                nested_data.get("detail"),
                result.get("error"),
                result.get("message"),
                result.get("detail"),
            )
            or "Command failed (nested data.success=false)"
        )
    return None
