"""Isolated Modbus configuration wizard helpers."""

from __future__ import annotations

import glob
from typing import Any

from oqlos.config import get_settings
from oqlos.api import hardware_modbus_topology as topology
from oqlos.api.hardware_modbus_settings import (
    MODBUS_BASELINE_BAUD,
    MODBUS_TARGET_BAUD_OPTIONS,
    build_init_baud_sequence,
    effective_modbus_adc_target_baud,
    effective_modbus_target_baud,
    normalize_probe_baudrates,
)
from oqlos.api.hardware_modbus_wizard_boundary import (
    _modbus_wizard_issue_for_exception,
    _raise_pimodbus_unavailable,
    _wizard_config_is_readable,
)

_settings = get_settings()

MODBUS_ISOLATED_PROBE_TIMEOUT = 0.2
_MODBUS_ROLE_ALIASES = {
    "io": "modbus-io",
    "modbus-io": "modbus-io",
    "adc": "modbus-adc",
    "modbus-adc": "modbus-adc",
}


def normalize_modbus_module_role(value: str) -> str:
    """Return the canonical role used by the probe, or an empty value."""
    return _MODBUS_ROLE_ALIASES.get(str(value or "").strip().lower(), "")


def _modbus_wizard_target_ids() -> list[int]:
    return sorted(set([*topology._modbus_io_device_ids(), int(_settings.modbus_adc_device_id)]))


def _modbus_wizard_plan() -> dict[str, Any]:
    io_ids = topology._modbus_io_device_ids()
    adc_id = int(_settings.modbus_adc_device_id)
    ports = topology._modbus_runtime_serial_ports()
    io_port = ports["io_serial_port"] or str(_settings.modbus_serial_port)
    adc_port = ports["adc_serial_port"] or io_port
    separate = ports["topology"] == "separate-adapters"
    target_baud = effective_modbus_target_baud(_settings)
    # ADC may use a different explicit override, but the C2004 bench baseline is 4800.
    adc_target_baud = effective_modbus_adc_target_baud(_settings)
    target_parity = str(_settings.modbus_parity).upper()
    adc_parity = str(getattr(_settings, "modbus_adc_parity", None) or _settings.modbus_parity).upper()

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
                "new_baudrate": adc_target_baud,
                "new_parity": adc_parity,
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
        "target_adc_baudrate": adc_target_baud,
        "target_parity": target_parity,
        "baseline_baudrate": MODBUS_BASELINE_BAUD,
        "baud_probe_sequence": build_init_baud_sequence(target_baud),
        "baudrate_options": list(MODBUS_TARGET_BAUD_OPTIONS),
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
        _raise_pimodbus_unavailable(
            operation_id="modbus.wizard.probe-isolated",
            cause=exc,
        )

    serial_candidates = _collect_wizard_serial_candidates(serial_port)
    target_max = effective_modbus_target_baud(_settings)
    scan_bauds = normalize_probe_baudrates(baudrates, target_max)

    all_scans: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    active_serial = serial_port
    for serial in serial_candidates:
        report = diagnose_shared_bus(
            serial_port=serial,
            target_baudrate=MODBUS_BASELINE_BAUD,
            target_parity=str(_settings.modbus_parity),
            io_device_id=int(_settings.modbus_device_id),
            adc_device_id=int(_settings.modbus_adc_device_id),
            baudrates=scan_bauds,
            parities=parities,
            device_ids=device_ids,
            timeout=MODBUS_ISOLATED_PROBE_TIMEOUT,
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
) -> "tuple[bool, dict, str, str | None]":
    """Read back device config with a stable, non-sensitive failure reason."""
    verify_reason = ""
    issue_code: str | None = None
    try:
        verify = read_device_config(verify_settings, device_id=new_device_id).to_dict()
    except Exception as exc:
        verify = {}
        verify_reason = "readback_failed"
        issue_code = _modbus_wizard_issue_for_exception(exc)
    verified = (
        int(verify.get("device_id") or -1) == new_device_id
        and int(verify.get("baudrate") or 0) == new_baudrate
        and str(verify.get("parity") or "").upper() == line_parity
    )
    return verified, verify, verify_reason, issue_code


def _wizard_build_result(
    writes: dict,
    verify: dict,
    verified: bool,
    new_device_id: int,
    new_baudrate: int,
    line_parity: str,
    serial_port: str,
    verify_reason: str,
    issue_code: str | None = None,
) -> dict:
    """Build the response dict for _modbus_wizard_program_isolated."""
    # A UART write can take effect before the device manages to echo its reply.
    # Conversely, optimistic write return values do not prove that the module is
    # listening with the requested settings.  Only a target-baud readback is a
    # successful commissioning result.
    ok = bool(verified)
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
    if verify_reason and not ok:
        result["error"] = verify_reason
    if issue_code and not ok:
        result["issue_code"] = issue_code
    return result


def _modbus_wizard_program_isolated(
    *,
    serial_port: str,
    current_device_id: int,
    new_device_id: int,
    new_baudrate: int,
    new_parity: str,
    confirm_isolated: bool,
    current_baudrate: int | None = None,
) -> dict[str, Any]:
    """Program isolated module: talk at current/baseline baud, then verify at target baud.

    Commissioning order (Waveshare RTU):
      1) open bus at *current* baud (probe hit or machine baseline 4800)
      2) write UART registers to *new* baud / parity
      3) re-open at *new* baud and verify device_id + UART
    """
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
        _raise_pimodbus_unavailable(
            operation_id="modbus.wizard.program-isolated",
            cause=exc,
        )

    line_parity = str(new_parity).upper()
    target_baud = int(new_baudrate)
    # Prefer probe-found baud, then machine baseline 4800, then target
    # (already-at-target case).
    open_baud_candidates: list[int] = []
    for baud in (
        int(current_baudrate) if current_baudrate else 0,
        MODBUS_BASELINE_BAUD,
        target_baud,
    ):
        if baud > 0 and baud not in open_baud_candidates:
            open_baud_candidates.append(baud)

    def _bus(baud: int) -> Any:
        return RtuBusSettings(
            serial_port=serial_port,
            baudrate=int(baud),
            parity=line_parity,
            timeout=2.0,
        )

    existing: dict[str, Any] = {}
    bus_settings = _bus(open_baud_candidates[0])
    open_baud_used = int(open_baud_candidates[0])
    config_read_reason = ""
    config_read_issue = "hw_modbus_no_response"
    for baud in open_baud_candidates:
        try:
            bus_settings = _bus(baud)
            candidate = read_device_config(
                bus_settings, device_id=int(current_device_id)
            ).to_dict()
            if not _wizard_config_is_readable(candidate):
                config_read_reason = "invalid_config_reply"
                config_read_issue = "hw_modbus_no_response"
                existing = {}
                continue
            existing = candidate
            open_baud_used = int(baud)
            config_read_reason = ""
            break
        except Exception as exc:
            config_read_reason = "config_read_failed"
            config_read_issue = _modbus_wizard_issue_for_exception(exc)
            existing = {}

    if not existing:
        return {
            "ok": False,
            "verified": False,
            "error": config_read_reason or "config_read_failed",
            "issue_code": config_read_issue,
            "open_baud_tried": open_baud_candidates,
            "target": {
                "device_id": int(new_device_id),
                "baudrate": target_baud,
                "parity": line_parity,
                "serial_port": serial_port,
            },
        }

    already_configured = _wizard_check_already_configured(
        existing, new_device_id, target_baud, line_parity
    )

    writes: dict[str, Any] = {
        "set_address": False,
        "set_uart": False,
        "skipped": already_configured,
        "open_baudrate": open_baud_used,
        "commissioning": {
            "phase": "baseline-then-target",
            "baseline_baud": MODBUS_BASELINE_BAUD,
            "open_baud": open_baud_used,
            "target_baud": target_baud,
        },
    }
    if already_configured:
        writes["set_address"] = True
        writes["set_uart"] = True
    else:
        # Writes must use the baud the module is *currently* listening on.
        uart_target = uart_register_value(target_baud, line_parity)
        cur_id = int(current_device_id)
        new_id = int(new_device_id)

        def _uart_register_value(device_id: int) -> int | None:
            client = _open_client(bus_settings)
            try:
                return _read_holding_register(client, UART_REGISTER, device_id)
            finally:
                client.close()

        write_results = _wizard_apply_uart_write(
            bus_settings, cur_id, new_id, uart_target, target_baud, line_parity,
            write_uart_config, write_device_address, _uart_register_value,
        )
        writes["set_address"] = write_results["set_address"]
        writes["set_uart"] = write_results["set_uart"]

    # After UART change, module listens at target baud — verify there.
    verify_settings = _bus(target_baud)
    verified, verify, verify_reason, verify_issue = _wizard_verify_config(
        read_device_config, verify_settings, int(new_device_id), target_baud, line_parity
    )
    result = _wizard_build_result(
        writes, verify, verified,
        int(new_device_id), target_baud, line_parity, serial_port, verify_reason,
        verify_issue,
    )
    result["commissioning"] = writes.get("commissioning")
    return result
