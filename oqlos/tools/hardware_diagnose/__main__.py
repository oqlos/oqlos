#!/usr/bin/env python3
"""
CLI entry point: python -m oqlos.tools.hardware_diagnose [options]

Usage:
  python -m oqlos.tools.hardware_diagnose               # interactive shell
  python -m oqlos.tools.hardware_diagnose --list         # USB/I2C list
  python -m oqlos.tools.hardware_diagnose --health       # firmware health
  python -m oqlos.tools.hardware_diagnose --diagnose     # full diagnostic
  python -m oqlos.tools.hardware_diagnose --calibrate    # calibration test
  python -m oqlos.tools.hardware_diagnose --benchmark 10 # 10s perf benchmark
  python -m oqlos.tools.hardware_diagnose --report       # save JSON report
  python -m oqlos.tools.hardware_diagnose --shell        # force interactive
"""

from __future__ import annotations

import argparse
import json

from .discovery import list_usb_serial_devices, list_i2c_buses
from .health import check_firmware_health, check_firmware_identify, cmd_health, cmd_diagnose
from .calibration import run_calibration_test
from .benchmark import run_benchmark
from .report import format_peripheral_table, save_diagnostic_report
from .shell import interactive_shell


def _print_list(url: str, as_json: bool) -> None:
    devices = list_usb_serial_devices()
    if as_json:
        print(json.dumps({"usb_devices": [d.to_dict() for d in devices], "i2c_buses": list_i2c_buses()}))
    else:
        print("\n🔌 USB/SERIAL PERIPHERALS")
        print(format_peripheral_table(devices))


def _print_health(url: str, as_json: bool) -> None:
    if as_json:
        print(json.dumps(check_firmware_health(url)))
    else:
        print(cmd_health(url))


def _print_calibrate(url: str, as_json: bool) -> None:
    results = run_calibration_test(url)
    if as_json:
        print(json.dumps(results))
        return
    print("\n🔧 CALIBRATION TEST RESULTS")
    print("═" * 50)
    print(f"Passed: {results['passed']}, Failed: {results['failed']}")
    for test in results["tests"]:
        icon = "✅" if test["passed"] else "❌"
        print(f"  {icon} {test['name']}: {test['details']}")
    if results["errors"]:
        print("\n⚠️  Errors:")
        for err in results["errors"]:
            print(f"    - {err}")


def _print_benchmark(url: str, duration: int, as_json: bool) -> None:
    results = run_benchmark(url, duration)
    if as_json:
        print(json.dumps(results))
        return
    print("\n⏱️  BENCHMARK RESULTS")
    print("═" * 50)
    if "error" in results:
        print(f"❌ {results['error']}")
    else:
        print(f"Requests: {results['requests']}")
        print(f"Errors:   {results['errors']}")
        print(f"Latency:  {results['latency_min_ms']:.1f}ms – {results['latency_max_ms']:.1f}ms")
        print(f"Average:  {results['latency_avg_ms']:.1f}ms  |  Median: {results['latency_median_ms']:.1f}ms")
        print(f"RPS:      {results['rps']:.1f}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hardware Diagnose CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--firmware-url", default="http://localhost:8202", help="Firmware base URL")
    parser.add_argument("--list",       action="store_true", help="List USB/serial/I2C peripherals")
    parser.add_argument("--health",     action="store_true", help="Check hardware health")
    parser.add_argument("--identify",   action="store_true", help="Detailed identification")
    parser.add_argument("--diagnose",   action="store_true", help="Full diagnostic")
    parser.add_argument("--calibrate",  action="store_true", help="Run calibration test")
    parser.add_argument("--benchmark",  type=int, nargs="?", const=10, metavar="SECONDS")
    parser.add_argument("--report",     nargs="?", const="auto", metavar="FILE",
                        help="Save diagnostic report (auto-generates filename)")
    parser.add_argument("--shell",      action="store_true", help="Interactive shell mode")
    parser.add_argument("--json",       action="store_true", help="Output as JSON")
    args = parser.parse_args()

    url = args.firmware_url
    jout = args.json
    action_given = any([
        args.list, args.health, args.identify, args.diagnose,
        args.calibrate, args.benchmark is not None, args.report, args.shell,
    ])

    if not action_given or args.shell:
        interactive_shell(url)
    elif args.list:
        _print_list(url, jout)
    elif args.health:
        _print_health(url, jout)
    elif args.identify:
        data = check_firmware_identify(url)
        print(json.dumps(data) if jout else json.dumps(data, indent=2, default=str))
    elif args.calibrate:
        _print_calibrate(url, jout)
    elif args.benchmark is not None:
        _print_benchmark(url, args.benchmark, jout)
    elif args.report:
        target = None if args.report == "auto" else args.report
        saved = save_diagnostic_report(target, url)
        print(json.dumps({"report_file": saved}) if jout else f"\n📄 Report saved to:\n   {saved}")
    elif args.diagnose:
        if jout:
            print(json.dumps({
                "usb_devices":       [d.to_dict() for d in list_usb_serial_devices()],
                "i2c_buses":         list_i2c_buses(),
                "firmware_health":   check_firmware_health(url),
                "firmware_identify": check_firmware_identify(url),
            }))
        else:
            print(cmd_diagnose(url))


if __name__ == "__main__":
    main()
