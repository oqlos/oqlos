"""Interactive hardware diagnostic REPL shell."""

from __future__ import annotations

import json

from .discovery import list_usb_serial_devices, list_i2c_buses, detect_chips_on_i2c
from .health import check_firmware_health, check_firmware_identify, cmd_health, cmd_diagnose
from .calibration import run_calibration_test
from .benchmark import run_benchmark
from .report import format_peripheral_table, save_diagnostic_report

_HELP_TEXT = """
Commands:
  list              - List detected USB/serial/I2C peripherals
  health            - Check firmware hardware health
  identify          - Detailed hardware identification
  test [pump|lung|valves|all] - Run smoke tests
  calibrate         - Run calibration test for all components
  benchmark [sec]   - Run performance benchmark (default 10s)
  save [file]       - Save diagnostic report to file
  diagnose          - Full diagnostic report
  json              - Output last identify result as JSON
  clear             - Clear screen
  exit/quit         - Exit shell
"""


def _cmd_list() -> None:
    devices = list_usb_serial_devices()
    print("\n🔌 USB/SERIAL PERIPHERALS")
    print(format_peripheral_table(devices))
    print("\n📡 I2C BUSES")
    buses = list_i2c_buses()
    if buses:
        for bus in buses:
            chips = detect_chips_on_i2c(bus)
            chip_str = f" ({len(chips)} chips)" if chips else ""
            print(f"  {bus}{chip_str}")
            for chip in chips[:5]:
                print(f"    └─ Address {chip['address']}")
    else:
        print("  No I2C buses detected.")


def _cmd_calibrate(url: str) -> None:
    print("\n🔧 Running calibration test...")
    results = run_calibration_test(url)
    print(f"Passed: {results['passed']}, Failed: {results['failed']}")
    for test in results["tests"]:
        status = "✅" if test["passed"] else "❌"
        print(f"  {status} {test['name']}: {test['details']}")
    if results["errors"]:
        print("⚠️  Errors:", results["errors"])


def _cmd_benchmark(parts: list[str], url: str) -> None:
    duration = 10
    if len(parts) > 1:
        try:
            duration = int(parts[1])
        except ValueError:
            pass
    results = run_benchmark(url, duration)
    if "error" not in results:
        print(f"\n⏱️  Benchmark ({duration}s):")
        print(f"  Requests: {results['requests']}, Errors: {results['errors']}")
        print(f"  Latency: {results['latency_avg_ms']:.1f}ms avg, {results['latency_median_ms']:.1f}ms median")
        print(f"  RPS: {results['rps']:.1f}")
    else:
        print(f"❌ {results['error']}")


def _dispatch_command(cmd: str, parts: list[str], url: str) -> bool:
    """Dispatch a single command. Returns False to exit shell."""
    # Exit commands
    if cmd in ("exit", "quit", "q"):
        print("Goodbye!")
        return False

    # Simple commands - mapped to their handlers
    simple_commands = {
        "help": lambda: print(_HELP_TEXT),
        "list": _cmd_list,
        "health": lambda: print(cmd_health(url)),
        "identify": lambda: print(json.dumps(check_firmware_identify(url), indent=2, default=str)),
        "diagnose": lambda: print(cmd_diagnose(url)),
        "clear": lambda: print("\033[2J\033[H", end=""),
        "calibrate": lambda: _cmd_calibrate(url),
        "save": lambda: print(f"\n📄 Report saved to: {save_diagnostic_report(None, url)}"),
        "json": lambda: print(json.dumps(check_firmware_identify(url))),
    }

    if cmd in simple_commands:
        simple_commands[cmd]()
        return True

    # Commands with arguments
    if parts[0] == "test":
        test_type = parts[1] if len(parts) > 1 else "all"
        print(f"\n🧪 Running {test_type} smoke test...")
        print("  (Smoke tests not yet implemented in shell)")
        return True

    if parts[0] == "benchmark":
        _cmd_benchmark(parts, url)
        return True

    # Unknown command
    print(f"Unknown command: {cmd!r}. Type 'help' for available commands.")
    return True


def interactive_shell(url: str = "http://localhost:8202") -> None:
    """Run the interactive hardware diagnostic REPL.

    Refactored from CC=18 to CC<10 using command dispatch table.
    """
    print("\n🔧 Hardware Diagnose Shell")
    print("Type 'help' for commands, 'exit' to quit.\n")

    while True:
        try:
            raw = input("hw-diagnose> ").strip()
            if not raw:
                continue

            cmd = raw.lower()
            parts = cmd.split()

            if not _dispatch_command(cmd, parts, url):
                break

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            break
