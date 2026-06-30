"""Rewrite OqlOS ``modbus_repair`` blocks for host runtime workflows."""

from __future__ import annotations

import os
from typing import Any


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip() or default


def _is_separate_adapters(payload: dict[str, Any]) -> bool:
    preflight = (
        payload.get("diagnostics", {}).get("modbus_preflight")
        if isinstance(payload.get("diagnostics"), dict)
        else None
    )
    if isinstance(preflight, dict) and preflight.get("topology") == "separate-adapters":
        return True
    return False


def _adapter_ports(payload: dict[str, Any]) -> tuple[str, str]:
    preflight = payload.get("diagnostics", {}).get("modbus_preflight") if isinstance(payload.get("diagnostics"), dict) else None
    io_port = ""
    adc_port = ""
    if isinstance(preflight, dict):
        for module in preflight.get("modules") or []:
            if module.get("plugin_id") == "modbus-io":
                io_port = str(module.get("bus", {}).get("serial_port") or "")
            elif module.get("plugin_id") == "modbus-adc":
                adc_port = str(module.get("bus", {}).get("serial_port") or "")
    return io_port, adc_port


def _augment_no_response_from_health(no_response: list[str], health: dict[str, Any]) -> list[str]:
    result = list(no_response)
    for plugin_id in ("modbus-io", "modbus-adc"):
        entry = health.get(plugin_id)
        if not isinstance(entry, dict) or entry.get("compatible"):
            continue
        message = str(entry.get("message") or "").lower()
        if plugin_id not in result and (
            "no response" in message
            or "timed out" in message
            or "errno 5" in message
            or "input/output error" in message
        ):
            result.append(plugin_id)
    return result


def _build_diagnose_cmd(target: dict[str, Any], io_port: str, adc_port: str, *, separate: bool) -> str:
    baud = target.get("baudrate", 9600)
    parity = target.get("parity", "N")
    io_id = target.get("io_device_id", 1)
    adc_id = target.get("adc_device_id", 2)
    target_serial = target.get("serial_port") or io_port
    oqlos_repo = _env("OQLOS_REPO", "/home/tom/github/oqlos/oqlos")
    oqlos_python = _env("OQLOS_PYTHON", "/home/tom/github/oqlos/oqlos/.venv/bin/python")
    if separate and io_port and adc_port:
        return (
            f"OQLOS_REPO={oqlos_repo} "
            f"OQLOS_PYTHON={oqlos_python} "
            f"MODBUS_PROBE_SERIALS=\"{adc_port},{io_port}\" "
            f"MODBUS_PROBE_BAUDS=\"{baud}\" "
            f"MODBUS_PROBE_DEVICE_IDS=\"{io_id},{adc_id}\" "
            f"MODBUS_PROBE_FUNCTIONS=\"read_coils,read_input_registers\" "
            "make hardware-modbus-probe"
        )
    return (
        f"cd {oqlos_repo} && "
        f"{oqlos_python} -m oqlos.tools.hardware_diagnose --modbus-probe "
        f"--serial {target_serial} --baud {baud} --parity {parity} "
        f"--device-id {io_id},{adc_id} --function read_coils,read_input_registers --timeout 1.5"
    )


def _build_safety_hints(
    no_response: list[str], health: dict[str, Any], existing_safety: list[str]
) -> tuple[list[str], str | None]:
    safety = list(existing_safety)
    operator_hint = (
        "Probe should start at the baseline Modbus speed (9600 baud). Only raise "
        "baud later after every module is stable and each device has been explicitly "
        "reconfigured. If no module answers at 9600, verify module power and RS485 "
        "wiring (A/B/GND) before rerunning identify."
    )
    stale_hint = (
        "Modbus plugins report [Errno 5] Input/output error: USB likely re-enumerated "
        "(ttyACM/ttyUSB numbers changed). Restart OqlOS before diagnose/repair."
    )
    health_stale = any(
        "errno 5" in str((health.get(pid) or {}).get("message") or "").lower()
        or "input/output error" in str((health.get(pid) or {}).get("message") or "").lower()
        for pid in ("modbus-io", "modbus-adc")
    )
    stale_reason: str | None = None
    if health_stale and stale_hint not in safety:
        safety.insert(0, stale_hint)
        stale_reason = stale_hint
    if no_response and operator_hint not in safety:
        safety.insert(0, operator_hint)
    only_io_silent = no_response == ["modbus-io"]
    if only_io_silent:
        io_only_hint = (
            "ADC responds, only Modbus IO 8CH is silent: the RS485 wiring on the "
            "ADC side is fine. Check the IO module's own power (7-36V on the "
            "module's terminal, NOT through USB), its A/B polarity, GND, and "
            "the slave id (factory default is 1; some units ship at a different "
            "id - try ids 1..10 and 247)."
        )
        if io_only_hint not in safety:
            safety.insert(0, io_only_hint)
    return safety, stale_reason


def rewrite_modbus_repair(payload: dict[str, Any]) -> dict[str, Any]:
    """Replace upstream docker-gateway commands with the configured host workflow."""
    if not isinstance(payload, dict):
        return payload

    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, dict):
        return payload

    repair = diagnostics.get("modbus_repair")
    if not isinstance(repair, dict) or not repair.get("available"):
        return payload

    health = diagnostics.get("health") if isinstance(diagnostics.get("health"), dict) else {}
    no_response = _augment_no_response_from_health(list(repair.get("no_response_modules") or []), health)
    repair["no_response_modules"] = no_response

    target = repair.get("target") if isinstance(repair.get("target"), dict) else {}
    io_port, adc_port = _adapter_ports(payload)
    separate = _is_separate_adapters(payload)
    c2004_root = _env("C2004_ROOT", "/home/tom/github/maskservice/c2004")
    oqlos_service = _env("OQLOS_HARDWARE_SERVICE", "oqlos-hardware-api.service")

    repair["commands"] = {
        "stop_firmware": f"systemctl --user stop {oqlos_service}",
        "diagnose": _build_diagnose_cmd(target, io_port, adc_port, separate=separate),
        "physical_checklist": (
            "Check 12V power on the Modbus module(s); A/B wires (try swapping); "
            "GND between module and adapter; 120 ohm termination; module slave ID "
            "(some Waveshare units ship at id=1 - collision if two on same bus)."
        ),
        "restart_firmware": f"cd {c2004_root} && make hardware-up",
    }

    safety, stale_reason = _build_safety_hints(no_response, health, list(repair.get("safety") or []))
    if stale_reason:
        repair["reason"] = stale_reason
    repair["safety"] = safety
    repair["topology"] = "separate-adapters" if separate else repair.get("topology")
    repair["adapters"] = {
        "modbus-io": {"serial_port": io_port, "device_id": target.get("io_device_id", 1)},
        "modbus-adc": {"serial_port": adc_port, "device_id": target.get("adc_device_id", 2)},
    }
    repair["source_overridden"] = "oqlos.hardware.client.modbus_repair"

    return payload
