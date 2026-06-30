"""Isolated Modbus configuration wizard helpers."""

from __future__ import annotations

import glob
import os
from typing import Any

from oqlos.config import get_settings
from oqlos.api import hardware_modbus_topology as topology

_settings = get_settings()

def _modbus_wizard_target_ids() -> list[int]:
    return sorted(set([*topology._modbus_io_device_ids(), int(_settings.modbus_adc_device_id)]))


def _modbus_wizard_plan() -> dict[str, Any]:
    io_ids = topology._modbus_io_device_ids()
    adc_id = int(_settings.modbus_adc_device_id)
    ports = topology._modbus_runtime_serial_ports()
    io_port = ports["io_serial_port"] or str(_settings.modbus_serial_port)
    adc_port = ports["adc_serial_port"] or io_port
    separate = ports["topology"] == "separate-adapters"
    target_baud = int(_settings.modbus_baud)
    target_parity = str(_settings.modbus_parity).upper()

    configure_steps: list[dict[str, Any]] = []
    for io_id in io_ids:
        configure_steps.append(
            {
                "step": f"configure-modbus-io-{io_id}",
                "serial_port": io_port,
                "instruction": (
                    f"Podlacz tylko modul Modbus IO na adapterze RS485 ({io_port}). "
                    "Odizoluj pozostale moduly od A/B."
                    if separate
                    else f"Podlacz tylko modul Modbus IO na RS485 ({io_port}). "
                    "Odizoluj pozostale moduly od A/B."
                ),
                "program_target": {
                    "module_role": "modbus-io",
                    "serial_port": io_port,
                    "new_device_id": io_id,
                    "new_baudrate": target_baud,
                    "new_parity": target_parity,
                },
            }
        )
    configure_steps.append(
        {
            "step": f"configure-modbus-adc-{adc_id}",
            "serial_port": adc_port,
            "instruction": (
                f"Podlacz tylko modul Modbus ADC na osobnym adapterze RS485 ({adc_port}). "
                "Odizoluj pozostale moduly od A/B."
                if separate
                else f"Podlacz tylko modul Modbus ADC na RS485 ({adc_port}). "
                "Odizoluj pozostale moduly od A/B."
            ),
            "program_target": {
                "module_role": "modbus-adc",
                "serial_port": adc_port,
                "new_device_id": adc_id,
                "new_baudrate": target_baud,
                "new_parity": target_parity,
            },
        }
    )
    configure_steps.append(
        {
            "step": "final-check-all-connected",
            "instruction": (
                "Oba moduly podlaczone do swoich adapterow USB (IO i ADC osobno) — uruchom finalna diagnostyke."
                if separate
                else "Podlacz wszystkie moduly razem i uruchom waveshare-diagnose."
            ),
            "verify_endpoint": "/api/v1/hardware/modbus/waveshare-diagnose",
        }
    )

    return {
        "ok": True,
        "serial_port": io_port,
        "io_serial_port": io_port,
        "adc_serial_port": adc_port,
        "topology": ports["topology"],
        "topology_mode": ports.get("topology_mode", "auto"),
        "target_baudrate": target_baud,
        "target_parity": target_parity,
        "target_ids": _modbus_wizard_target_ids(),
        "steps": configure_steps,
    }


def _collect_wizard_serial_candidates(serial_port: str) -> list[str]:
    """Build list of serial ports to probe, starting with any explicit port."""
    requested = str(serial_port or "").strip()
    if requested:
        return [requested]
    candidates: list[str] = []
    for value in [str(_settings.modbus_serial_port), str(_settings.modbus_adc_serial_port)]:
        value = str(value or "").strip()
        if value and value not in candidates:
            candidates.append(value)
    for discovered in sorted(
        glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*") + glob.glob("/dev/serial/by-id/*")
    ):
        if discovered and discovered not in candidates:
            candidates.append(discovered)
    return candidates


def _modbus_wizard_probe_isolated(
    serial_port: str,
    baudrates: list[int],
    parities: list[str],
    device_ids: list[int],
    required_roles: list[str] | None = None,
) -> dict[str, Any]:
    try:
        from pimodbus.repair import diagnose_shared_bus
    except Exception as exc:
        return {"ok": False, "error": f"pimodbus is not available: {exc}"}

    serial_candidates = _collect_wizard_serial_candidates(serial_port)

    all_scans: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    active_serial = serial_port
    for serial in serial_candidates:
        report = diagnose_shared_bus(
            serial_port=serial,
            target_baudrate=int(_settings.modbus_baud),
            target_parity=str(_settings.modbus_parity),
            io_device_id=int(_settings.modbus_device_id),
            adc_device_id=int(_settings.modbus_adc_device_id),
            baudrates=baudrates,
            parities=parities,
            device_ids=device_ids,
            timeout=1.0,
            scan_all_ports=False,
            required_roles=required_roles,
        )
        report_dict = report.to_dict()
        all_scans.append({"serial_port": serial, "scan": report_dict})
        hits = list(report_dict.get("hits") or [])
        current_candidates = [
            {
                "role": hit.get("role"),
                "device_id": int(hit.get("device_id", 0)),
                "baudrate": int(hit.get("baudrate", 0)),
                "parity": str(hit.get("parity") or ""),
                "serial_port": str(hit.get("serial_port") or serial),
            }
            for hit in hits
        ]
        if current_candidates:
            candidates = current_candidates
            active_serial = serial
            break

    report_dict = all_scans[-1]["scan"] if all_scans else {"ok": False, "hits": [], "issues": []}
    return {
        "ok": bool(candidates),
        "serial_port": active_serial,
        "candidates": candidates,
        "scan": report_dict,
        "all_scans": all_scans,
    }


def _wizard_check_already_configured(
    existing: "dict[str, Any]",
    new_device_id: int,
    new_baudrate: int,
    line_parity: str,
) -> bool:
    """Return True when existing device config already matches the target settings."""
    existing_id = int(existing.get("device_id") or -1)
    existing_baud = int(existing.get("baudrate") or 0)
    existing_parity = str(existing.get("parity") or "").upper()
    return (
        existing_id == int(new_device_id)
        and existing_baud == int(new_baudrate)
        and existing_parity == line_parity
    )


def _wizard_apply_uart_write(
    bus_settings: Any,
    cur_id: int,
    new_id: int,
    uart_target: int,
    new_baudrate: int,
    line_parity: str,
    write_uart_config: Any,
    write_device_address: Any,
    _uart_register_value: Any,
) -> "dict[str, bool]":
    """Write UART config and device address with retry loop. Returns {set_address, set_uart}."""
    import time

    uart_at_current = _uart_register_value(cur_id)
    if uart_at_current is not None and int(uart_at_current) == int(uart_target):
        set_uart = True
    else:
        set_uart = bool(
            write_uart_config(
                bus_settings,
                device_id=cur_id,
                baudrate=int(new_baudrate),
                parity=line_parity,
            )
        )

    if cur_id != new_id:
        set_address = bool(
            write_device_address(
                bus_settings,
                current_device_id=cur_id,
                new_device_id=new_id,
            )
        )
        time.sleep(0.2)
    else:
        set_address = True

    if not set_uart:
        for attempt, device_id in enumerate((new_id, new_id, cur_id)):
            if attempt == 1:
                time.sleep(0.15)
            uart_value = _uart_register_value(device_id)
            if uart_value is not None and int(uart_value) == int(uart_target):
                set_uart = True
                break
        if not set_uart:
            set_uart = bool(
                write_uart_config(
                    bus_settings,
                    device_id=new_id,
                    baudrate=int(new_baudrate),
                    parity=line_parity,
                )
            )

    return {"set_address": set_address, "set_uart": set_uart}


def _wizard_verify_config(
    read_device_config: Any,
    verify_settings: Any,
    new_device_id: int,
    new_baudrate: int,
    line_parity: str,
) -> "tuple[bool, dict, str]":
    """Read back device config after programming; return (verified, verify_dict, error_str)."""
    verify_error = ""
    try:
        verify = read_device_config(verify_settings, device_id=new_device_id).to_dict()
    except Exception as exc:
        verify = {}
        verify_error = str(exc)
    verified = (
        int(verify.get("device_id") or -1) == new_device_id
        and int(verify.get("baudrate") or 0) == new_baudrate
        and str(verify.get("parity") or "").upper() == line_parity
    )
    return verified, verify, verify_error


def _wizard_build_result(
    writes: dict,
    verify: dict,
    verified: bool,
    new_device_id: int,
    new_baudrate: int,
    line_parity: str,
    serial_port: str,
    verify_error: str,
) -> dict:
    """Build the response dict for _modbus_wizard_program_isolated."""
    ok = bool(verified or (writes["set_address"] and writes["set_uart"]))
    result: dict[str, Any] = {
        "ok": ok,
        "writes": writes,
        "verify": verify,
        "target": {
            "device_id": new_device_id,
            "baudrate": new_baudrate,
            "parity": line_parity,
            "serial_port": serial_port,
        },
        "verified": bool(verified),
    }
    if verify_error and not ok:
        result["error"] = verify_error
    return result


def _modbus_wizard_program_isolated(
    *,
    serial_port: str,
    current_device_id: int,
    new_device_id: int,
    new_baudrate: int,
    new_parity: str,
    confirm_isolated: bool,
) -> dict[str, Any]:
    if not confirm_isolated:
        return {
            "ok": False,
            "error": "Refusing to write Modbus configuration without confirm_isolated=true",
        }
    try:
        from pimodbus.config import RtuBusSettings
        from pimodbus.provisioning import (
            UART_REGISTER,
            read_device_config,
            uart_register_value,
            write_device_address,
            write_uart_config,
            _open_client,
            _read_holding_register,
        )
    except Exception as exc:
        return {"ok": False, "error": f"pimodbus is not available: {exc}"}

    line_parity = str(new_parity).upper()
    bus_settings = RtuBusSettings(
        serial_port=serial_port,
        baudrate=int(new_baudrate),
        parity=line_parity,
        timeout=2.0,
    )

    verify_settings = bus_settings
    config_read_error = ""
    try:
        existing = read_device_config(verify_settings, device_id=int(current_device_id)).to_dict()
    except Exception as exc:
        config_read_error = str(exc)
        if int(current_device_id) == int(new_device_id):
            return {
                "ok": True,
                "verified": False,
                "writes": {
                    "set_address": True,
                    "set_uart": True,
                    "skipped": True,
                    "config_read_error": config_read_error,
                },
                "verify": {},
                "target": {
                    "device_id": int(new_device_id),
                    "baudrate": int(new_baudrate),
                    "parity": line_parity,
                    "serial_port": serial_port,
                },
                "note": "Probe reported target slave ID; skipped provisioning writes (config registers unreadable).",
            }
        return {"ok": False, "error": config_read_error}

    already_configured = _wizard_check_already_configured(existing, new_device_id, new_baudrate, line_parity)

    writes: dict[str, Any] = {
        "set_address": False,
        "set_uart": False,
        "skipped": already_configured,
    }
    if already_configured:
        writes["set_address"] = True
        writes["set_uart"] = True
    else:
        uart_target = uart_register_value(int(new_baudrate), line_parity)
        cur_id = int(current_device_id)
        new_id = int(new_device_id)

        def _uart_register_value(device_id: int) -> int | None:
            client = _open_client(bus_settings)
            try:
                return _read_holding_register(client, UART_REGISTER, device_id)
            finally:
                client.close()

        write_results = _wizard_apply_uart_write(
            bus_settings, cur_id, new_id, uart_target, new_baudrate, line_parity,
            write_uart_config, write_device_address, _uart_register_value,
        )
        writes["set_address"] = write_results["set_address"]
        writes["set_uart"] = write_results["set_uart"]

    verified, verify, verify_error = _wizard_verify_config(
        read_device_config, verify_settings, int(new_device_id), int(new_baudrate), line_parity
    )
    return _wizard_build_result(
        writes, verify, verified,
        int(new_device_id), int(new_baudrate), line_parity, serial_port, verify_error,
    )
