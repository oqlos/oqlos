"""Waveshare Modbus RTU scan matrix and diagnose report builders."""

from __future__ import annotations

from typing import Any

from oqlos.config import get_settings
from oqlos.api import hardware_modbus_topology as topology
from oqlos.api.hardware_gateway import is_plugin_compatible as _is_plugin_compatible

_settings = get_settings()


def _diagnose_shared_bus_matrix(
    *,
    serial_port: str,
    target_baudrate: int,
    target_parity: str,
    io_device_id: int,
    adc_device_id: int,
    device_ids: list[int],
    required_roles: list[str] | None = None,
    timeout_fast: float = 0.5,
    timeout_full: float = 0.35,
):
    from pimodbus.repair import diagnose_shared_bus

    baud_sequence = [4800, 9600, 19200, 38400, 57600, 115200]
    target_report = diagnose_shared_bus(
        serial_port=serial_port,
        target_baudrate=target_baudrate,
        target_parity=target_parity,
        io_device_id=io_device_id,
        adc_device_id=adc_device_id,
        baudrates=[int(target_baudrate)],
        parities=[str(target_parity).upper()],
        device_ids=device_ids,
        timeout=timeout_fast,
        scan_all_ports=True,
        required_roles=required_roles,
    )
    if target_report.ok:
        return target_report
    return diagnose_shared_bus(
        serial_port=serial_port,
        target_baudrate=target_baudrate,
        target_parity=target_parity,
        io_device_id=io_device_id,
        adc_device_id=adc_device_id,
        baudrates=baud_sequence,
        parities=["N", "E", "O"],
        device_ids=device_ids,
        timeout=timeout_full,
        scan_all_ports=True,
        required_roles=required_roles,
    )


def _merge_unique_text_list(existing: list[str], new_items: "list[Any]") -> None:
    """Append string items from new_items to existing, skipping duplicates."""
    for item in new_items or []:
        text = str(item)
        if text and text not in existing:
            existing.append(text)


def _merge_waveshare_scan_dicts(*reports: dict[str, Any]) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    recommendations: list[str] = []
    actions: list[dict[str, Any]] = []
    targets: list[dict[str, Any]] = []
    for report in reports:
        if not isinstance(report, dict):
            continue
        hits.extend(list(report.get("hits") or []))
        issues.extend(list(report.get("issues") or []))
        _merge_unique_text_list(recommendations, report.get("recommendations"))
        actions.extend(list(report.get("actions") or []))
        target = report.get("target")
        if isinstance(target, dict):
            targets.append(target)
    merged_target = targets[0] if len(targets) == 1 else {"buses": targets}
    return {
        "ok": False,
        "safe_to_auto_apply": all(bool(report.get("safe_to_auto_apply")) for report in reports if isinstance(report, dict)),
        "target": merged_target,
        "hits": hits,
        "issues": issues,
        "actions": actions,
        "recommendations": recommendations,
        "probe_summary": reports[-1].get("probe_summary") if reports else {},
    }


def _read_output_control_modes(
    serial_port: str,
    baudrate: int,
    parity: str,
    device_id: int,
    timeout: float = 1.5,
) -> dict[str, Any]:
    try:
        from pymodbus.client import ModbusSerialClient  # type: ignore
    except Exception as exc:
        return {"ok": False, "error": f"pymodbus unavailable: {exc}"}

    client = ModbusSerialClient(
        port=serial_port,
        baudrate=int(baudrate),
        parity=str(parity),
        stopbits=1,
        bytesize=8,
        timeout=float(timeout),
    )
    try:
        if not client.connect():
            return {"ok": False, "error": f"Cannot open serial port {serial_port}"}
        result = client.read_holding_registers(address=0x1000, count=8, device_id=int(device_id))
        if not result or result.isError():
            return {"ok": False, "error": "Failed to read holding registers 0x1000..0x1007"}
        registers = list(getattr(result, "registers", []) or [])
        return {"ok": True, "registers": registers}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        try:
            client.close()
        except Exception:
            pass


def _modbus_plugins_healthy(health: dict[str, Any] | None) -> bool:
    """True when both Modbus plugins report compatible (ports held by firmware)."""
    if not isinstance(health, dict):
        return False
    return _is_plugin_compatible(health.get("modbus-io")) and _is_plugin_compatible(
        health.get("modbus-adc")
    )


def _modbus_health_serial_stale(health: dict[str, Any] | None) -> bool:
    """True when Modbus plugins hit EIO — typical after USB re-enumeration (tty remap)."""
    if not isinstance(health, dict):
        return False
    for plugin_id in ("modbus-io", "modbus-adc"):
        entry = health.get(plugin_id)
        if not isinstance(entry, dict):
            continue
        message = str(entry.get("message") or "").lower()
        if "errno 5" in message or "input/output error" in message:
            return True
    return False


def _build_waveshare_serial_stale_report(
    health: dict[str, Any],
    *,
    ports: dict[str, Any],
    io_ids: list[int],
    adc_id: int,
    baud_sequence: list[int],
) -> dict[str, Any]:
    """Do not run matrix scan on stale handles — restart OqlOS to reopen tty/by-id."""
    io_port = ports["io_serial_port"] or str(_settings.modbus_serial_port)
    adc_port = ports["adc_serial_port"] or io_port
    skip_reason = "Modbus serial handle stale (USB re-enumeration); restart OqlOS"
    per_slave: dict[str, Any] = {}
    for io_id in io_ids:
        per_slave[f"modbus-io-{io_id}"] = {
            "ok": False,
            "status": "serial-stale",
            "device_id": io_id,
            "source": "plugin-health",
            "message": str((health.get("modbus-io") or {}).get("message") or skip_reason),
        }
    per_slave[f"modbus-adc-{adc_id}"] = {
        "ok": False,
        "status": "serial-stale",
        "device_id": adc_id,
        "source": "plugin-health",
        "message": str((health.get("modbus-adc") or {}).get("message") or skip_reason),
    }
    return {
        "ok": False,
        "serial_handles_stale": True,
        "baud_sequence": baud_sequence,
        "io_device_ids": io_ids,
        "adc_device_id": adc_id,
        "topology": ports["topology"],
        "io_serial_port": io_port,
        "adc_serial_port": adc_port,
        "waveshare_scan": {
            "ok": False,
            "scan_skipped": True,
            "scan_skip_reason": skip_reason,
            "issues": [
                {
                    "severity": "error",
                    "code": "serial_handle_stale",
                    "message": skip_reason,
                    "roles": ["modbus-io", "modbus-adc"],
                }
            ],
            "recommendations": [
                "USB adapters are visible but OqlOS still holds old tty handles (e.g. ttyACM1→ttyACM2).",
                "Run: cd c2004 && make hardware-oqlos-only",
                "Or: systemctl --user restart oqlos-hardware-api.service",
                "Then refresh hardware-status before running valve/ADC tests.",
            ],
            "topology": ports["topology"],
            "ports_scanned": [
                {"role": "modbus-io", "serial_port": io_port},
                {"role": "modbus-adc", "serial_port": adc_port},
            ],
        },
        "per_slave": per_slave,
    }


def _build_waveshare_from_plugin_health(
    health: dict[str, Any],
    *,
    ports: dict[str, Any],
    io_ids: list[int],
    adc_id: int,
    target_baud: int,
    target_parity: str,
    baud_sequence: list[int],
) -> dict[str, Any]:
    """Skip RS485 matrix scan when OqlOS plugins already own the serial ports."""
    io_port = ports["io_serial_port"] or str(_settings.modbus_serial_port)
    adc_port = ports["adc_serial_port"] or io_port
    separate = ports["topology"] == "separate-adapters"
    skip_reason = "plugin owns Modbus serial port; inline scan skipped"
    per_slave: dict[str, Any] = {}
    hits: list[dict[str, Any]] = []

    for io_id in io_ids:
        key = f"modbus-io-{io_id}"
        per_slave[key] = {
            "ok": True,
            "status": "connected",
            "device_id": io_id,
            "source": "plugin-health",
            "message": str((health.get("modbus-io") or {}).get("message") or "Modbus RTU is healthy"),
            "detected": {
                "serial_port": io_port,
                "baudrate": target_baud,
                "parity": target_parity,
            },
            "output_modes_registers_0x1000_0x1007": {
                "ok": None,
                "skipped": True,
                "reason": skip_reason,
            },
        }
        hits.append(
            {
                "role": "modbus-io",
                "serial_port": io_port,
                "baudrate": target_baud,
                "parity": target_parity,
                "device_id": io_id,
                "function": "read_coils",
                "source": "plugin-health",
            }
        )

    adc_key = f"modbus-adc-{adc_id}"
    per_slave[adc_key] = {
        "ok": True,
        "status": "connected",
        "device_id": adc_id,
        "source": "plugin-health",
        "message": str((health.get("modbus-adc") or {}).get("message") or "Modbus ADC is healthy"),
        "detected": {
            "serial_port": adc_port,
            "baudrate": target_baud,
            "parity": target_parity,
        },
    }
    hits.append(
        {
            "role": "modbus-adc",
            "serial_port": adc_port,
            "baudrate": target_baud,
            "parity": target_parity,
            "device_id": adc_id,
            "function": "read_input_registers",
            "source": "plugin-health",
        }
    )

    scan_target: dict[str, Any]
    if separate:
        scan_target = {
            "buses": [
                {
                    "serial_port": io_port,
                    "baudrate": target_baud,
                    "parity": target_parity,
                    "io_device_id": int(_settings.modbus_device_id),
                    "adc_device_id": adc_id,
                },
                {
                    "serial_port": adc_port,
                    "baudrate": target_baud,
                    "parity": target_parity,
                    "io_device_id": int(_settings.modbus_device_id),
                    "adc_device_id": adc_id,
                },
            ]
        }
        ports_scanned = [
            {"role": "modbus-io", "serial_port": io_port},
            {"role": "modbus-adc", "serial_port": adc_port},
        ]
    else:
        scan_target = {
            "serial_port": io_port,
            "baudrate": target_baud,
            "parity": target_parity,
            "io_device_id": int(_settings.modbus_device_id),
            "adc_device_id": adc_id,
        }
        ports_scanned = []

    return {
        "ok": True,
        "baud_sequence": baud_sequence,
        "io_device_ids": io_ids,
        "adc_device_id": adc_id,
        "topology": ports["topology"],
        "io_serial_port": io_port,
        "adc_serial_port": adc_port,
        "waveshare_scan": {
            "ok": True,
            "safe_to_auto_apply": False,
            "scan_skipped": True,
            "scan_skip_reason": skip_reason,
            "target": scan_target,
            "hits": hits,
            "issues": [],
            "actions": [],
            "recommendations": [
                "Modbus IO/ADC are healthy via OqlOS plugins. For UART/register deep-check, "
                "use hardware restart wizard (exclusive scan) or stop OqlOS before pimodbus diagnose.",
            ],
            "topology": ports["topology"],
            "ports_scanned": ports_scanned,
        },
        "per_slave": per_slave,
        "plugin_health_deferred": True,
    }


def _probe_waveshare_separate(
    io_port: str,
    adc_port: str,
    target_baud: int,
    target_parity: str,
    io_device_id: int,
    io_ids: list,
    adc_id: int,
) -> tuple[dict, bool]:
    """Probe two separate RS485 adapters; return (merged_report_dict, ok)."""
    io_report = _diagnose_shared_bus_matrix(
        serial_port=io_port,
        target_baudrate=target_baud,
        target_parity=target_parity,
        io_device_id=io_device_id,
        adc_device_id=adc_id,
        device_ids=io_ids,
        required_roles=["modbus-io"],
    )
    adc_report = _diagnose_shared_bus_matrix(
        serial_port=adc_port,
        target_baudrate=target_baud,
        target_parity=target_parity,
        io_device_id=io_device_id,
        adc_device_id=adc_id,
        device_ids=[adc_id],
        required_roles=["modbus-adc"],
    )
    report_ok = bool(io_report.ok and adc_report.ok)
    report_dict = _merge_waveshare_scan_dicts(io_report.to_dict(), adc_report.to_dict())
    report_dict["ok"] = report_ok
    report_dict["topology"] = "separate-adapters"
    report_dict["ports_scanned"] = [
        {"role": "modbus-io", "serial_port": io_port},
        {"role": "modbus-adc", "serial_port": adc_port},
    ]
    return report_dict, report_ok


def _probe_waveshare_shared_bus(
    io_port: str,
    target_baud: int,
    target_parity: str,
    io_device_id: int,
    adc_id: int,
    target_ids: list,
) -> tuple[dict, bool]:
    """Probe a single shared RS485 bus; return (report_dict, ok)."""
    report = _diagnose_shared_bus_matrix(
        serial_port=io_port,
        target_baudrate=target_baud,
        target_parity=target_parity,
        io_device_id=io_device_id,
        adc_device_id=adc_id,
        device_ids=target_ids,
    )
    report_dict = report.to_dict()
    report_dict["topology"] = "shared-bus"
    return report_dict, bool(report.ok)


def _read_waveshare_io_slave_config(
    io_id: int,
    io_hits: list,
    io_port: str,
    target_baud: int,
    target_parity: str,
) -> dict:
    """Read device config and control modes for one modbus-io slave; return per-slave dict."""
    from pimodbus.config import RtuBusSettings
    from pimodbus.provisioning import read_device_config
    hit = next((entry for entry in io_hits if int(entry.get("device_id", -1)) == io_id), None)
    if not hit:
        return {
            "ok": False,
            "status": "no-response",
            "device_id": io_id,
            "message": "No Modbus RTU response for this slave id in Waveshare scan matrix",
        }
    settings = RtuBusSettings(
        serial_port=str(hit.get("serial_port") or io_port),
        baudrate=int(hit.get("baudrate") or target_baud),
        parity=str(hit.get("parity") or target_parity),
        timeout=1.5,
    )
    try:
        config = read_device_config(settings, device_id=io_id).to_dict()
    except Exception as exc:
        return {
            "ok": False,
            "status": "read-error",
            "device_id": io_id,
            "message": str(exc),
        }
    control_modes = _read_output_control_modes(
        settings.serial_port,
        settings.baudrate,
        settings.parity,
        io_id,
        timeout=settings.timeout,
    )
    return {
        "ok": True,
        "status": "ok",
        "device_id": io_id,
        "detected": {
            "serial_port": settings.serial_port,
            "baudrate": settings.baudrate,
            "parity": settings.parity,
            "function": hit.get("function"),
        },
        "slave_address_register_0x4000": config.get("device_id"),
        "uart_register_0x2000": {
            "baudrate": config.get("baudrate"),
            "parity": config.get("parity"),
        },
        "output_modes_registers_0x1000_0x1007": control_modes,
    }


def _read_waveshare_adc_slave_config(
    adc_id: int,
    adc_hits: list,
    adc_port: str,
    target_baud: int,
    target_parity: str,
) -> dict:
    """Read device config for the modbus-adc slave; return per-slave dict."""
    from pimodbus.config import RtuBusSettings
    from pimodbus.provisioning import read_device_config
    adc_hit = next((entry for entry in adc_hits if int(entry.get("device_id", -1)) == adc_id), None)
    if not adc_hit:
        return {
            "ok": False,
            "status": "no-response",
            "device_id": adc_id,
            "message": "No Modbus RTU response for ADC slave id in Waveshare scan matrix",
        }
    settings = RtuBusSettings(
        serial_port=str(adc_hit.get("serial_port") or adc_port),
        baudrate=int(adc_hit.get("baudrate") or target_baud),
        parity=str(adc_hit.get("parity") or target_parity),
        timeout=1.5,
    )
    try:
        config = read_device_config(settings, device_id=adc_id).to_dict()
    except Exception as exc:
        return {
            "ok": False,
            "status": "read-error",
            "device_id": adc_id,
            "message": str(exc),
        }
    return {
        "ok": True,
        "status": "ok",
        "device_id": adc_id,
        "detected": {
            "serial_port": settings.serial_port,
            "baudrate": settings.baudrate,
            "parity": settings.parity,
            "function": adc_hit.get("function"),
        },
        "slave_address_register_0x4000": config.get("device_id"),
        "uart_register_0x2000": {
            "baudrate": config.get("baudrate"),
            "parity": config.get("parity"),
        },
    }


def _resolve_waveshare_ports(ports: "dict[str, Any]") -> "tuple[str, str]":
    """Return (io_port, adc_port) resolving fallbacks from settings."""
    io_port = ports["io_serial_port"] or str(_settings.modbus_serial_port)
    adc_port = ports["adc_serial_port"] or io_port
    return io_port, adc_port


def _split_hits_by_role(hits: list) -> "tuple[list, list]":
    """Split scan hits into (io_hits, adc_hits) by role field."""
    io_hits = [h for h in hits if h.get("role") == "modbus-io"]
    adc_hits = [h for h in hits if h.get("role") == "modbus-adc"]
    return io_hits, adc_hits


def _build_waveshare_diagnose_report(health: dict[str, Any] | None = None) -> dict[str, Any]:
    baud_sequence = [4800, 9600, 19200, 38400, 57600, 115200]
    io_ids = topology._modbus_io_device_ids()
    adc_id = int(_settings.modbus_adc_device_id)
    target_ids = sorted(set([*io_ids, adc_id]))
    ports = topology._modbus_runtime_serial_ports()
    separate = ports["topology"] == "separate-adapters"
    io_port, adc_port = _resolve_waveshare_ports(ports)

    target_baud = int(_settings.modbus_baud)
    target_parity = str(_settings.modbus_parity)
    io_device_id = int(_settings.modbus_device_id)

    if _modbus_plugins_healthy(health):
        return _build_waveshare_from_plugin_health(
            health or {},
            ports=ports,
            io_ids=io_ids,
            adc_id=adc_id,
            target_baud=target_baud,
            target_parity=target_parity,
            baud_sequence=baud_sequence,
        )

    if _modbus_health_serial_stale(health):
        return _build_waveshare_serial_stale_report(
            health or {},
            ports=ports,
            io_ids=io_ids,
            adc_id=adc_id,
            baud_sequence=baud_sequence,
        )

    try:
        import pimodbus.config  # noqa: F401
        import pimodbus.provisioning  # noqa: F401
    except Exception as exc:
        return {
            "ok": False,
            "error": f"pimodbus is not available: {exc}",
            "baud_sequence": baud_sequence,
            "io_device_ids": io_ids,
            "adc_device_id": adc_id,
            "topology": ports["topology"],
        }

    if separate:
        report_dict, report_ok = _probe_waveshare_separate(
            io_port, adc_port, target_baud, target_parity, io_device_id, io_ids, adc_id
        )
    else:
        report_dict, report_ok = _probe_waveshare_shared_bus(
            io_port, target_baud, target_parity, io_device_id, adc_id, target_ids
        )

    hits = list(report_dict.get("hits") or [])
    io_hits, adc_hits = _split_hits_by_role(hits)

    per_slave: dict[str, Any] = {}
    for io_id in io_ids:
        per_slave[f"modbus-io-{io_id}"] = _read_waveshare_io_slave_config(
            io_id, io_hits, io_port, target_baud, target_parity
        )

    per_slave[f"modbus-adc-{adc_id}"] = _read_waveshare_adc_slave_config(
        adc_id, adc_hits, adc_port, target_baud, target_parity
    )

    return {
        "ok": report_ok,
        "baud_sequence": baud_sequence,
        "io_device_ids": io_ids,
        "adc_device_id": adc_id,
        "topology": ports["topology"],
        "io_serial_port": io_port,
        "adc_serial_port": adc_port,
        "waveshare_scan": report_dict,
        "per_slave": per_slave,
    }
