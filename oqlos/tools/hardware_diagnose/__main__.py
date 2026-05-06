#!/usr/bin/env python3
"""
CLI entry point: python -m oqlos.tools.hardware_diagnose [options]

Usage:
  python -m oqlos.tools.hardware_diagnose               # interactive shell
  python -m oqlos.tools.hardware_diagnose --list         # USB/I2C list
  python -m oqlos.tools.hardware_diagnose --detect       # smart local detection
  python -m oqlos.tools.hardware_diagnose --doctor       # diagnose config/runtime issues
  python -m oqlos.tools.hardware_diagnose --health       # firmware health
  python -m oqlos.tools.hardware_diagnose --modbus-probe # direct Modbus RTU probe
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
from .doctor import build_doctor_report, detect_hardware, format_detection, format_doctor
from .modbus_probe import add_modbus_probe_arguments, run_modbus_probe_from_args
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


def _print_detect(url: str, as_json: bool, config_path: str | None) -> None:
    result = detect_hardware(url, config_path=config_path)
    print(json.dumps(result) if as_json else format_detection(result))


def _print_doctor(url: str, as_json: bool, config_path: str | None, fix: bool) -> None:
    result = build_doctor_report(url, config_path=config_path, fix=fix)
    print(json.dumps(result) if as_json else format_doctor(result))


def _print_modbus_probe(_as_json: bool, args: argparse.Namespace) -> None:
    result = run_modbus_probe_from_args(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("ok") else 2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hardware Diagnose CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--firmware-url", default="http://localhost:8202", help="Firmware base URL")
    parser.add_argument("--config",      help="Path to oqlos.yaml (default: auto-detect)")
    parser.add_argument("--list",       action="store_true", help="List USB/serial/I2C peripherals")
    parser.add_argument("--detect",     action="store_true", help="Run smart local hardware detection")
    parser.add_argument("--doctor",     action="store_true", help="Diagnose OqlOS hardware config/runtime issues")
    parser.add_argument("--fix",        action="store_true", help="Apply safe doctor repairs")
    parser.add_argument("--health",     action="store_true", help="Check hardware health")
    parser.add_argument("--identify",   action="store_true", help="Detailed identification")
    parser.add_argument("--modbus-probe", action="store_true", help="Probe Modbus RTU directly with MODBUS_* env")
    parser.add_argument("--diagnose",   action="store_true", help="Full diagnostic")
    parser.add_argument("--calibrate",  action="store_true", help="Run calibration test")
    parser.add_argument("--benchmark",  type=int, nargs="?", const=10, metavar="SECONDS")
    parser.add_argument("--report",     nargs="?", const="auto", metavar="FILE",
                        help="Save diagnostic report (auto-generates filename)")
    parser.add_argument("--shell",      action="store_true", help="Interactive shell mode")
    parser.add_argument("--json",       action="store_true", help="Output as JSON")
    add_modbus_probe_arguments(parser)
    args = parser.parse_args()

    url = args.firmware_url
    jout = args.json
    action_given = any([
        args.list, args.detect, args.doctor, args.fix, args.health, args.identify, args.diagnose,
        args.modbus_probe, args.calibrate, args.benchmark is not None, args.report, args.shell,
    ])

    if not action_given or args.shell:
        interactive_shell(url)
    elif args.detect:
        _print_detect(url, jout, args.config)
    elif args.doctor or args.fix:
        _print_doctor(url, jout, args.config, args.fix)
    elif args.list:
        _print_list(url, jout)
    elif args.health:
        _print_health(url, jout)
    elif args.modbus_probe:
        _print_modbus_probe(jout, args)
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
