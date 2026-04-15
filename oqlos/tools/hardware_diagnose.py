#!/usr/bin/env python3
"""
Hardware Diagnose CLI — Interactive hardware detection and testing tool.

Usage:
  python -m oqlos.tools.hardware_diagnose
  python -m oqlos.tools.hardware_diagnose --auto-test
  python -m oqlos.tools.hardware_diagnose --shell

Commands (in shell mode):
  list              - List detected USB/serial peripherals
  health            - Check all hardware health
  identify          - Detailed hardware identification
  test [pump|lung|valves|all] - Run smoke tests
  diagnose          - Full diagnostic report
  exit/quit         - Exit shell
"""
from __future__ import annotations

import argparse
import json
import sys
import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

# USB/Serial detection
try:
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False


def _run_shell_command(cmd: list[str]) -> tuple[int, str, str]:
    """Run shell command and return (rc, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)


@dataclass
class UsbDevice:
    """USB device information."""
    device: str
    vid: Optional[int]
    pid: Optional[int]
    manufacturer: Optional[str]
    product: Optional[str]
    serial_number: Optional[str]
    description: str

    def to_dict(self) -> dict:
        return {
            "device": self.device,
            "vid": f"0x{self.vid:04X}" if self.vid else None,
            "pid": f"0x{self.pid:04X}" if self.pid else None,
            "manufacturer": self.manufacturer,
            "product": self.product,
            "serial": self.serial_number,
            "description": self.description,
        }


def list_usb_serial_devices() -> list[UsbDevice]:
    """Detect all USB-to-serial devices."""
    devices = []
    
    # Method 1: pyserial
    if HAS_SERIAL:
        for port in serial.tools.list_ports.comports():
            devices.append(UsbDevice(
                device=port.device,
                vid=port.vid,
                pid=port.pid,
                manufacturer=port.manufacturer,
                product=port.product,
                serial_number=port.serial_number,
                description=port.description or "Unknown",
            ))
    
    # Method 2: ls /dev/tty*
    rc, stdout, _ = _run_shell_command(["ls", "-la", "/dev/ttyACM*", "/dev/ttyUSB*"])
    if rc == 0:
        for line in stdout.split("\n"):
            if "ttyACM" in line or "ttyUSB" in line:
                parts = line.split()
                if len(parts) >= 10:
                    device = f"/dev/{parts[-1]}"
                    if not any(d.device == device for d in devices):
                        devices.append(UsbDevice(
                            device=device,
                            vid=None,
                            pid=None,
                            manufacturer=None,
                            product=None,
                            serial_number=None,
                            description="USB Serial (from ls)",
                        ))
    
    return devices


def list_i2c_buses() -> list[str]:
    """List available I2C buses."""
    rc, stdout, _ = _run_shell_command(["ls", "-la", "/dev/i2c-*"])
    buses = []
    if rc == 0:
        for line in stdout.split("\n"):
            if "/dev/i2c-" in line:
                parts = line.split()
                if len(parts) >= 10:
                    buses.append(f"/dev/{parts[-1]}")
    return buses


def detect_chips_on_i2c(bus: str = "/dev/i2c-1") -> list[dict]:
    """Detect chips on I2C bus using i2cdetect."""
    rc, stdout, _ = _run_shell_command(["i2cdetect", "-y", bus.replace("/dev/i2c-", "")])
    chips = []
    if rc == 0:
        # Parse i2cdetect output
        for line in stdout.split("\n")[1:]:  # Skip header
            if line.strip() and not line.startswith("   "):
                parts = line.split()
                if len(parts) > 1:
                    row = parts[0].rstrip(":")
                    for i, addr in enumerate(parts[1:9], start=0):
                        if addr not in ["--", "UU"]:
                            full_addr = f"0x{row}{i:X}"
                            chips.append({
                                "address": full_addr,
                                "raw": addr,
                                "bus": bus,
                            })
    return chips


def format_peripheral_table(devices: list[UsbDevice]) -> str:
    """Format USB devices as ASCII table."""
    # Filter out virtual serial ports (ttyS*), keep only real USB devices
    real_devices = [d for d in devices if d.vid is not None or 
                    ("ttyACM" in d.device or "ttyUSB" in d.device)]
    
    if not real_devices:
        return "No USB/serial devices detected."
    
    lines = [
        "═" * 80,
        f"{'DEVICE':15} | {'VID:PID':10} | {'PRODUCT':25} | {'MANUFACTURER'}",
        "─" * 80,
    ]
    
    for d in real_devices:
        vid_pid = f"{d.vid:04X}:{d.pid:04X}" if d.vid and d.pid else "-"
        product = (d.product or d.description or "-")[:25]
        mfr = (d.manufacturer or "-")[:20]
        lines.append(f"{d.device:15} | {vid_pid:10} | {product:25} | {mfr}")
    
    lines.append("═" * 80)
    return "\n".join(lines)


def cmd_list() -> str:
    """List command - show all detected hardware."""
    output = []
    output.append("\n🔌 USB/SERIAL PERIPHERALS")
    output.append(format_peripheral_table(list_usb_serial_devices()))
    
    output.append("\n📡 I2C BUSES")
    buses = list_i2c_buses()
    if buses:
        for bus in buses:
            chips = detect_chips_on_i2c(bus)
            chip_str = f" ({len(chips)} chips)" if chips else ""
            output.append(f"  {bus}{chip_str}")
            for chip in chips[:5]:  # Limit to first 5
                output.append(f"    └─ Address {chip['address']}")
    else:
        output.append("  No I2C buses detected.")
    
    return "\n".join(output)


def check_firmware_health(url: str = "http://localhost:8202") -> dict:
    """Check firmware health via HTTP API."""
    try:
        import httpx
        r = httpx.get(f"{url}/api/v1/hardware/health", timeout=5.0)
        return r.json() if r.status_code == 200 else {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def check_firmware_identify(url: str = "http://localhost:8202") -> dict:
    """Get detailed hardware identification."""
    try:
        import httpx
        r = httpx.get(f"{url}/api/v1/hardware/identify", timeout=5.0)
        return r.json() if r.status_code == 200 else {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def cmd_health(url: str = "http://localhost:8202") -> str:
    """Health command - check firmware health."""
    health = check_firmware_health(url)
    
    output = ["\n🏥 HARDWARE HEALTH"]
    output.append("─" * 50)
    
    if "error" in health:
        output.append(f"❌ Error: {health['error']}")
    else:
        mode = health.get("mode", "unknown")
        output.append(f"Mode: {mode.upper()}")
        
        for key, val in health.items():
            if key != "mode":
                status = "✅" if val in ["ok", "connected", True] else "⚠️"
                output.append(f"  {status} {key}: {val}")
    
    return "\n".join(output)


def cmd_diagnose(url: str = "http://localhost:8202") -> str:
    """Full diagnostic command."""
    output = []
    output.append("\n" + "=" * 60)
    output.append("HARDWARE DIAGNOSTIC REPORT")
    output.append("=" * 60)
    
    # USB devices
    output.append(cmd_list())
    
    # Firmware health
    output.append(cmd_health(url))
    
    # Detailed identify
    identify = check_firmware_identify(url)
    if "error" not in identify:
        output.append("\n🔍 FIRMWARE IDENTIFY")
        output.append("─" * 50)
        output.append(json.dumps(identify, indent=2, default=str))
    
    output.append("\n" + "=" * 60)
    return "\n".join(output)


def run_calibration_test(url: str = "http://localhost:8202") -> dict:
    """Run calibration test for all hardware components.
    
    Returns dict with calibration results and any errors.
    """
    import httpx
    import time
    
    results = {
        "timestamp": time.time(),
        "tests": [],
        "passed": 0,
        "failed": 0,
        "errors": []
    }
    
    def log_test(name: str, passed: bool, details: str = ""):
        results["tests"].append({
            "name": name,
            "passed": passed,
            "details": details
        })
        if passed:
            results["passed"] += 1
        else:
            results["failed"] += 1
            results["errors"].append(f"{name}: {details}")
    
    try:
        with httpx.Client() as client:
            # Test 1: Pump calibration - check response time
            start = time.time()
            r = client.post(f"{url}/api/v1/hardware/pump", 
                          json={"power": 10}, timeout=2.0)
            response_time = (time.time() - start) * 1000
            
            if r.status_code == 200:
                log_test("pump_response", True, f"Response: {response_time:.1f}ms")
                
                # Stop pump
                client.post(f"{url}/api/v1/hardware/pump", 
                          json={"power": 0}, timeout=2.0)
            else:
                log_test("pump_response", False, f"HTTP {r.status_code}")
            
            # Test 2: Valve calibration - sequence test
            valves = ["valve-nc", "valve-sc", "valve-wc"]
            for valve in valves:
                try:
                    r = client.post(f"{url}/api/v1/hardware/valve/{valve}",
                                  json={"value": True}, timeout=2.0)
                    if r.status_code == 200:
                        # Close valve
                        client.post(f"{url}/api/v1/hardware/valve/{valve}",
                                  json={"value": False}, timeout=2.0)
                        log_test(f"{valve}_calibration", True, "Open/Close OK")
                    else:
                        log_test(f"{valve}_calibration", False, f"HTTP {r.status_code}")
                except Exception as e:
                    log_test(f"{valve}_calibration", False, str(e))
            
            # Test 3: Sensor readings
            sensors = ["nc-sensor", "sc-sensor", "wc-sensor"]
            for sensor in sensors:
                try:
                    r = client.get(f"{url}/api/v1/hardware/sensor/{sensor}", timeout=2.0)
                    if r.status_code == 200:
                        data = r.json()
                        value = data.get("value", 0)
                        # Check if sensor reading is in reasonable range (0-5000 mbar)
                        if 0 <= value <= 5000:
                            log_test(f"{sensor}_reading", True, f"Value: {value}")
                        else:
                            log_test(f"{sensor}_reading", False, f"Out of range: {value}")
                    else:
                        log_test(f"{sensor}_reading", False, f"HTTP {r.status_code}")
                except Exception as e:
                    log_test(f"{sensor}_reading", False, str(e))
                
    except Exception as e:
        results["errors"].append(f"Calibration error: {e}")
    
    return results


def run_benchmark(url: str = "http://localhost:8202", duration: int = 10) -> dict:
    """Run performance benchmark.
    
    Args:
        duration: Test duration in seconds
    """
    import httpx
    import time
    import statistics
    
    latencies = []
    errors = 0
    start_time = time.time()
    
    print(f"\n⏱️  Running benchmark for {duration}s...")
    
    with httpx.Client() as client:
        while time.time() - start_time < duration:
            try:
                t0 = time.time()
                r = client.get(f"{url}/api/v1/hardware/health", timeout=1.0)
                latency = (time.time() - t0) * 1000
                
                if r.status_code == 200:
                    latencies.append(latency)
                else:
                    errors += 1
            except Exception:
                errors += 1
            
            time.sleep(0.1)  # 10 requests per second max
    
    if latencies:
        return {
            "requests": len(latencies),
            "errors": errors,
            "latency_min_ms": min(latencies),
            "latency_max_ms": max(latencies),
            "latency_avg_ms": statistics.mean(latencies),
            "latency_median_ms": statistics.median(latencies),
            "rps": len(latencies) / duration
        }
    else:
        return {"error": "No successful requests", "errors": errors}


def save_diagnostic_report(filename: str = None, url: str = "http://localhost:8202") -> str:
    """Save full diagnostic report to file.
    
    Returns path to saved report.
    """
    import time
    from pathlib import Path
    
    if filename is None:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"hw_diagnostic_{timestamp}.json"
    
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
    with open(filepath, "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    return str(filepath.absolute())


def interactive_shell(url: str = "http://localhost:8202"):
    """Run interactive shell."""
    print("\n🔧 Hardware Diagnose Shell")
    print("Type 'help' for commands, 'exit' to quit.\n")
    
    while True:
        try:
            cmd = input("hw-diagnose> ").strip().lower()
            
            if cmd in ["exit", "quit", "q"]:
                print("Goodbye!")
                break
            
            elif cmd == "help":
                print("""
Commands:
  list              - List detected USB/serial/I2C peripherals
  health            - Check firmware hardware health
  identify          - Detailed hardware identification
  test [pump|lung|valves|all] - Run smoke tests
  calibrate         - Run calibration test for all components
  benchmark [sec]   - Run performance benchmark (default 10s)
  save [file]       - Save diagnostic report to file
  diagnose          - Full diagnostic report
  json              - Output last result as JSON
  clear             - Clear screen
  exit/quit         - Exit shell
                """)
            
            elif cmd == "list":
                print(cmd_list())
            
            elif cmd == "health":
                print(cmd_health(url))
            
            elif cmd == "identify":
                identify = check_firmware_identify(url)
                print(json.dumps(identify, indent=2, default=str))
            
            elif cmd == "diagnose":
                print(cmd_diagnose(url))
            
            elif cmd == "clear":
                print("\033[2J\033[H", end="")
            
            elif cmd.startswith("test "):
                test_type = cmd.split()[1] if len(cmd.split()) > 1 else "all"
                print(f"\n🧪 Running {test_type} smoke test...")
                # TODO: Implement smoke test runner
                print("  (Smoke tests not yet implemented in shell)")
            
            elif cmd == "calibrate":
                print("\n🔧 Running calibration test...")
                results = run_calibration_test(url)
                print(f"Passed: {results['passed']}, Failed: {results['failed']}")
                for test in results['tests']:
                    status = "✅" if test['passed'] else "❌"
                    print(f"  {status} {test['name']}: {test['details']}")
                if results['errors']:
                    print("⚠️  Errors:", results['errors'])
            
            elif cmd == "benchmark":
                duration = 10
                if len(cmd.split()) > 1:
                    try:
                        duration = int(cmd.split()[1])
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
            
            elif cmd == "save":
                saved_path = save_diagnostic_report(None, url)
                print(f"\n📄 Report saved to: {saved_path}")
            
            elif cmd == "json":
                # Output last identify result as JSON for shell parsing
                identify = check_firmware_identify(url)
                print(json.dumps(identify))
            
            elif cmd:
                print(f"Unknown command: {cmd}. Type 'help' for available commands.")
        
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            break


def main():
    parser = argparse.ArgumentParser(
        description="Hardware Diagnose CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list                    # List USB peripherals
  %(prog)s --health                  # Check health
  %(prog)s --diagnose                # Full diagnostic
  %(prog)s --calibrate               # Run calibration tests
  %(prog)s --benchmark [sec]         # Run performance benchmark
  %(prog)s --report [file]           # Save diagnostic report
  %(prog)s --shell                   # Interactive shell
  %(prog)s --json                    # JSON output for scripts
        """
    )
    parser.add_argument("--firmware-url", default="http://localhost:8202",
                        help="Firmware URL (default: http://localhost:8202)")
    parser.add_argument("--list", action="store_true", help="List USB/serial peripherals")
    parser.add_argument("--health", action="store_true", help="Check hardware health")
    parser.add_argument("--identify", action="store_true", help="Detailed identification")
    parser.add_argument("--diagnose", action="store_true", help="Full diagnostic")
    parser.add_argument("--calibrate", action="store_true", help="Run calibration test")
    parser.add_argument("--benchmark", type=int, nargs="?", const=10, metavar="SECONDS",
                        help="Run performance benchmark (default: 10s)")
    parser.add_argument("--report", nargs="?", const="auto", metavar="FILE",
                        help="Save diagnostic report (auto-generates filename)")
    parser.add_argument("--shell", action="store_true", help="Interactive shell mode")
    parser.add_argument("--json", action="store_true", help="Output as JSON for shell scripts")
    
    args = parser.parse_args()
    
    # Default to shell if no args
    if not any([args.list, args.health, args.identify, args.diagnose, 
                args.calibrate, args.benchmark is not None, args.report, args.shell]):
        args.shell = True
    
    if args.shell:
        interactive_shell(args.firmware_url)
    elif args.list:
        if args.json:
            devices = [d.to_dict() for d in list_usb_serial_devices()]
            print(json.dumps({"usb_devices": devices, "i2c_buses": list_i2c_buses()}))
        else:
            print(cmd_list())
    elif args.health:
        if args.json:
            print(json.dumps(check_firmware_health(args.firmware_url)))
        else:
            print(cmd_health(args.firmware_url))
    elif args.identify:
        identify = check_firmware_identify(args.firmware_url)
        if args.json:
            print(json.dumps(identify))
        else:
            print(json.dumps(identify, indent=2, default=str))
    elif args.calibrate:
        results = run_calibration_test(args.firmware_url)
        if args.json:
            print(json.dumps(results))
        else:
            print("\n🔧 CALIBRATION TEST RESULTS")
            print("═" * 50)
            print(f"Passed: {results['passed']}, Failed: {results['failed']}")
            for test in results['tests']:
                status = "✅" if test['passed'] else "❌"
                print(f"  {status} {test['name']}: {test['details']}")
            if results['errors']:
                print("\n⚠️  Errors:")
                for err in results['errors']:
                    print(f"    - {err}")
    elif args.benchmark is not None:
        results = run_benchmark(args.firmware_url, args.benchmark)
        if args.json:
            print(json.dumps(results))
        else:
            print("\n⏱️  BENCHMARK RESULTS")
            print("═" * 50)
            if "error" in results:
                print(f"❌ {results['error']}")
            else:
                print(f"Requests: {results['requests']}")
                print(f"Errors: {results['errors']}")
                print(f"Latency: {results['latency_min_ms']:.1f}ms - {results['latency_max_ms']:.1f}ms")
                print(f"Average: {results['latency_avg_ms']:.1f}ms")
                print(f"Median: {results['latency_median_ms']:.1f}ms")
                print(f"RPS: {results['rps']:.1f}")
    elif args.report:
        filename = None if args.report == "auto" else args.report
        saved_path = save_diagnostic_report(filename, args.firmware_url)
        if args.json:
            print(json.dumps({"report_file": saved_path}))
        else:
            print(f"\n📄 Diagnostic report saved to:")
            print(f"   {saved_path}")
    elif args.diagnose:
        if args.json:
            # Structure JSON output for shell parsing
            result = {
                "usb_devices": [d.to_dict() for d in list_usb_serial_devices()],
                "i2c_buses": list_i2c_buses(),
                "firmware_health": check_firmware_health(args.firmware_url),
                "firmware_identify": check_firmware_identify(args.firmware_url),
            }
            print(json.dumps(result))
        else:
            print(cmd_diagnose(args.firmware_url))


if __name__ == "__main__":
    main()

