"""Smart hardware detection and doctor-style repair suggestions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from oqlos.hardware.discovery import probe_waveshare_modbus, probe_waveshare_modbus_adc
from oqlos.tools.hardware_diagnose.discovery import (
    UsbDevice,
    list_i2c_buses,
    list_usb_serial_devices,
)
from oqlos.tools.hardware_diagnose.health import (
    check_firmware_health,
    check_firmware_identify,
)
from oqlos.tools.hardware_diagnose.doctor_common import Issue, collect_repairs
from oqlos.tools.hardware_diagnose.doctor_detection import detect_hardware
from oqlos.tools.hardware_diagnose.doctor_firmware import analyze_firmware_access
from oqlos.tools.hardware_diagnose.doctor_format import format_detection, format_doctor
from oqlos.tools.hardware_diagnose.doctor_modbus_analysis import (
    analyze_modbus_adc_config,
    analyze_modbus_config,
    analyze_serial_port_owners,
)
from oqlos.tools.hardware_diagnose.doctor_repairs import apply_safe_fixes
from oqlos.tools.hardware_diagnose.doctor_serial import (
    canonical_device_path as _canonical_device_path,
    serial_port_owners as _serial_port_owners,
)

__all__ = [
    "UsbDevice",
    "apply_safe_fixes",
    "build_doctor_report",
    "check_firmware_health",
    "check_firmware_identify",
    "detect_hardware",
    "format_detection",
    "format_doctor",
    "list_i2c_buses",
    "list_usb_serial_devices",
    "probe_waveshare_modbus",
    "probe_waveshare_modbus_adc",
]


def build_doctor_report(
    firmware_url: str = "http://localhost:8202",
    *,
    config_path: str | Path | None = None,
    probe_timeout: float = 0.35,
    fix: bool = False,
) -> dict[str, Any]:
    """Run smart detection, analyze problems, and optionally apply safe fixes."""
    detection = detect_hardware(
        firmware_url,
        config_path=config_path,
        probe_timeout=probe_timeout,
        include_firmware=True,
    )
    issues: list[Issue] = []
    analyze_modbus_config(detection, issues)
    analyze_modbus_adc_config(detection, issues)
    analyze_serial_port_owners(detection, issues)
    analyze_firmware_access(detection, issues)

    repairs = collect_repairs(issues)
    applied: list[dict[str, Any]] = []
    if fix:
        applied = apply_safe_fixes(detection, repairs, config_path=config_path)
        for repair in repairs:
            if any(item.get("id") == repair.get("id") for item in applied):
                repair["applied"] = True

    error_count = sum(1 for issue in issues if issue["severity"] == "error")
    warn_count = sum(1 for issue in issues if issue["severity"] == "warn")
    return {
        "ok": error_count == 0,
        "status": "ok" if error_count == 0 and warn_count == 0 else "needs_attention",
        "summary": {
            "errors": error_count,
            "warnings": warn_count,
            "repairs": len(repairs),
            "applied_repairs": len(applied),
        },
        "detection": detection,
        "issues": issues,
        "repairs": repairs,
        "applied_repairs": applied,
        "fix_requested": fix,
    }
