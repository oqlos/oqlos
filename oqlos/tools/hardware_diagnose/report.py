"""Diagnostic report formatting and persistence."""

from __future__ import annotations

import json
import time
from pathlib import Path

from .discovery import UsbDevice, list_usb_serial_devices, list_i2c_buses
from .health import check_firmware_health, check_firmware_identify
from .calibration import run_calibration_test


def format_peripheral_table(devices: list[UsbDevice]) -> str:
    """Format USB devices as an ASCII table.

    Filters out virtual serial ports (ttyS*), keeping only real USB devices.
    """
    real = [d for d in devices if d.vid is not None or ("ttyACM" in d.device or "ttyUSB" in d.device)]
    if not real:
        return "No USB/serial devices detected."

    lines = [
        "═" * 80,
        f"{'DEVICE':15} | {'VID:PID':10} | {'PRODUCT':25} | {'MANUFACTURER'}",
        "─" * 80,
    ]
    for d in real:
        vid_pid = f"{d.vid:04X}:{d.pid:04X}" if d.vid and d.pid else "-"
        product = (d.product or d.description or "-")[:25]
        mfr = (d.manufacturer or "-")[:20]
        lines.append(f"{d.device:15} | {vid_pid:10} | {product:25} | {mfr}")
    lines.append("═" * 80)
    return "\n".join(lines)


def save_diagnostic_report(filename: str | None = None, url: str = "http://localhost:8202") -> str:
    """Save full diagnostic report as JSON.

    Args:
        filename: Target path (auto-generates timestamped name when None).
        url:      Firmware base URL.

    Returns:
        Absolute path to saved report file.
    """
    if filename is None:
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"hw_diagnostic_{ts}.json"

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "firmware_url": url,
        "usb_devices": [d.to_dict() for d in list_usb_serial_devices()],
        "i2c_buses": list_i2c_buses(),
        "firmware_health": check_firmware_health(url),
        "firmware_identify": check_firmware_identify(url),
        "calibration": run_calibration_test(url),
    }

    filepath = Path(filename)
    filepath.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return str(filepath.absolute())
