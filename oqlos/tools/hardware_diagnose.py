#!/usr/bin/env python3
"""
oqlos.tools.hardware_diagnose (legacy compatibility shim)

This module has been refactored into a package:
  oqlos.tools.hardware_diagnose/
    discovery.py   — USB/I2C detection
    health.py      — firmware health & identify
    calibration.py — calibration test runner
    benchmark.py   — performance benchmark
    report.py      — report formatting & saving
    shell.py       — interactive REPL

All original symbols are re-exported here for backward compatibility.
"""

# ruff: noqa: F401
from oqlos.tools.hardware_diagnose import (  # noqa: F401  # type: ignore[import]
    UsbDevice,
    check_firmware_health,
    check_firmware_identify,
    cmd_diagnose,
    cmd_health,
    detect_chips_on_i2c,
    format_peripheral_table,
    interactive_shell,
    list_i2c_buses,
    list_usb_serial_devices,
    run_benchmark,
    run_calibration_test,
    save_diagnostic_report,
)
from oqlos.tools.hardware_diagnose.__main__ import main  # noqa: F401  # type: ignore[import]

if __name__ == "__main__":
    main()
