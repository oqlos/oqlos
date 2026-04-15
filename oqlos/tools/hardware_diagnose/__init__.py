"""
oqlos.tools.hardware_diagnose — Hardware detection, health, calibration, and benchmarking.

Sub-modules:
  discovery   — USB/serial/I2C detection
  health      — Firmware health & identification
  calibration — Calibration test runner
  benchmark   — Performance benchmark
  report      — Diagnostic report generation & formatting
  shell       — Interactive REPL shell
"""

from .discovery import (
    UsbDevice,
    list_usb_serial_devices,
    list_i2c_buses,
    detect_chips_on_i2c,
)
from .health import (
    check_firmware_health,
    check_firmware_identify,
    cmd_health,
    cmd_diagnose,
)
from .calibration import run_calibration_test
from .benchmark import run_benchmark
from .report import format_peripheral_table, save_diagnostic_report
from .shell import interactive_shell
from .__main__ import main

__all__ = [
    # discovery
    "UsbDevice",
    "list_usb_serial_devices",
    "list_i2c_buses",
    "detect_chips_on_i2c",
    # health
    "check_firmware_health",
    "check_firmware_identify",
    "cmd_health",
    "cmd_diagnose",
    # calibration
    "run_calibration_test",
    # benchmark
    "run_benchmark",
    # report
    "format_peripheral_table",
    "save_diagnostic_report",
    # shell
    "interactive_shell",
    # cli
    "main",
]
