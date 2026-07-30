"""Live USB/serial/I2C hardware probing helpers."""

from __future__ import annotations

import glob
import inspect
from typing import Any

from oqlos.api import hardware_platform as platform
from oqlos.api.hardware_gateway import is_plugin_compatible as _is_plugin_compatible, try_get_hardware_gateway
from oqlos.api.hardware_probe_devices import (
    _local_ads1115_probe_allowed,  # noqa: F401 - compatibility re-export
    _probe_configured_waveshare_rtu,
    _probe_dri0050,
    _probe_i2c_ads1115,  # noqa: F401 - compatibility re-export
    _probe_tic249,
    _probe_waveshare_rtu,  # noqa: F401 - compatibility re-export
    _scan_usb_devices,
)
from oqlos.api.hardware_registry import HARDWARE_REGISTRY
from oqlos.config import get_settings
from oqlos.errors.c2004_catalog_generated import c2004_code_for_issue
from oqlos.hardware.discovery import list_serial_ports

_settings = get_settings()


def _probe_all_hardware(ids: set[str] | None = None) -> dict[str, Any]:
    """Run selected hardware probes and return combined result."""
    selected = ids or {hw["id"] for hw in HARDWARE_REGISTRY}
    usb_devices: list[dict[str, str]] | None = None
    results: dict[str, Any] = {}

    if "motor-tic249" in selected or "motor-dri0050" in selected:
        usb_devices = _scan_usb_devices()
    if "motor-tic249" in selected:
        results["motor-tic249"] = _probe_tic249(usb_devices or [])
    if "motor-dri0050" in selected:
        results["motor-dri0050"] = _probe_dri0050(usb_devices or [])
    if "modbus-adc" in selected:
        results["modbus-adc"] = _probe_configured_waveshare_rtu("modbus-adc")
    if "modbus-io" in selected:
        results["modbus-io"] = _probe_configured_waveshare_rtu("modbus-io")
    return results


def _collect_hardware_diagnostics() -> dict[str, Any]:
    """Collect best-effort port and bus inventory for troubleshooting."""
    return {
        "platform": platform._detect_runtime_platform(),
        "usb_devices": _scan_usb_devices(),
        "serial_ports": list_serial_ports(),
        "i2c_buses": sorted(glob.glob("/dev/i2c-*")),
        "modbus_preflight": _modbus_preflight_report(),
    }


def _needs_live_scan(health: dict[str, Any]) -> bool:
    """Run expensive live scan only when at least one registered adapter is not compatible."""
    for hw in HARDWARE_REGISTRY:
        if not _is_plugin_compatible(health.get(hw["id"])):
            return True
    return False


def _unhealthy_plugin_ids(health: dict[str, Any]) -> set[str]:
    """Return adapter ids whose plugin health is not compatible."""
    return {
        hw["id"]
        for hw in HARDWARE_REGISTRY
        if not _is_plugin_compatible(health.get(hw["id"]))
    }


def _modbus_health_is_no_response(health_entry: dict[str, Any]) -> bool:
    """Return True when the serial adapter is open but the Modbus device is silent."""
    message = str(health_entry.get("message") or "")
    return (
        "read_coils" in message
        or "read_input_registers" in message
        or "No response" in message
        or "timed out" in message
    )


def _probe_selected_hardware(ids: set[str]) -> dict[str, Any]:
    """Run selected probes while staying compatible with older monkeypatched tests."""
    if len(inspect.signature(_probe_all_hardware).parameters) == 0:
        return _probe_all_hardware()  # type: ignore[call-arg]
    return _probe_all_hardware(ids)


def _modbus_preflight_report() -> dict[str, Any]:
    gateway = try_get_hardware_gateway()
    if gateway is not None and hasattr(gateway, "modbus_preflight_report"):
        try:
            report = gateway.modbus_preflight_report()
            if isinstance(report, dict):
                return report
        except (ImportError, OSError, RuntimeError, ValueError):
            issue_code = "modbus_preflight_exception"
            return {
                "ok": False,
                "topology": "unknown",
                "modules": [],
                "issues": [
                    {
                        "severity": "error",
                        "code": issue_code,
                        "public_code": c2004_code_for_issue(issue_code),
                        "message": "Modbus preflight could not produce a report",
                        "modules": ["modbus-io", "modbus-adc"],
                        "repair": {},
                    }
                ],
                "recommended": {},
                "diagnostics": {
                    "issue_code": issue_code,
                    "code": c2004_code_for_issue(issue_code),
                },
            }
    return {"ok": True, "topology": "unknown", "modules": [], "issues": [], "recommended": {}}


def _modbus_repair_guidance(health: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        from pimodbus.repair import build_runtime_repair_guidance
    except ImportError:
        return {
            "available": False,
            "error": "pimodbus-repair-unavailable",
            "diagnostics": {
                "issue_code": "pimodbus_unavailable",
                "code": c2004_code_for_issue("pimodbus_unavailable"),
            },
        }

    return build_runtime_repair_guidance(
        serial_port=_settings.modbus_serial_port,
        baudrate=_settings.modbus_baud,
        parity=_settings.modbus_parity,
        io_device_id=_settings.modbus_device_id,
        adc_device_id=_settings.modbus_adc_device_id,
        health=health or {},
    )
