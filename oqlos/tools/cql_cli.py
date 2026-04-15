"""
CQL CLI entry point — run, validate, and batch-check .cql/.oql scenario files.

Usage:
  oqlctl file.cql
  oqlctl file.cql --mode validate
  oqlctl --validate-dir scenarios/
  oqlctl cmd "SET 'pompa 1' '0'"
  python -m oqlos.tools.cql_cli file.oql --mode dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import textwrap
import time
import sys
from pathlib import Path

import click
import httpx
import yaml

from oqlos.core.cql_parser import parse_cql
from oqlos.core.interpreter import CqlInterpreter
from oqlos.hardware.firmware_adapter import _PERIPHERAL_MAP
from oqlos.tools.hardware_diagnose.health import check_firmware_health, check_firmware_identify


DEFAULT_FIRMWARE_URL = "http://localhost:8202"


def _output_yaml(data: dict, quiet: bool = False) -> None:
    """Output data as YAML to stdout."""
    if not quiet:
        print(yaml.dump(data, default_flow_style=False, sort_keys=False), end="")


def _ensure_firmware_running(firmware_url: str, *, quiet: bool, yaml_output: bool = False) -> bool:
    """Attempt to start firmware service if it's not available."""
    # First check if already running
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{firmware_url}/health")
            if resp.status_code < 300:
                if not quiet and not yaml_output:
                    click.echo(f"✓ Firmware already running at {firmware_url}", err=True)
                return True
    except Exception:
        pass

    # Not running - try to start it
    if not quiet and not yaml_output:
        click.echo(f"⏳ Firmware not available at {firmware_url}, attempting to start...", err=True)

    try:
        # Start oqlos-server in background
        process = subprocess.Popen(
            [sys.executable, "-m", "oqlos.api.main"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        
        # Wait for it to become healthy (max 10 seconds)
        max_wait = 10
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                with httpx.Client(timeout=1.0) as client:
                    resp = client.get(f"{firmware_url}/health")
                    if resp.status_code < 300:
                        if not quiet and not yaml_output:
                            click.echo(f"✓ Firmware started successfully at {firmware_url}", err=True)
                        return True
            except Exception:
                time.sleep(0.5)
        
        if not quiet and not yaml_output:
            click.echo(f"❌ Firmware did not start within {max_wait}s", err=True)
        process.terminate()
        return False
    except Exception as exc:
        if not quiet and not yaml_output:
            click.echo(f"❌ Failed to start firmware: {exc}", err=True)
        return False


def _parse_sensor_overrides(sensor_args: list[str]) -> dict[str, float]:
    """Parse `-s name=value` overrides into a sensor mapping."""
    sensors: dict[str, float] = {}
    for s in sensor_args:
        if "=" not in s:
            continue
        key, value = s.split("=", 1)
        sensors[key.strip()] = float(value.strip())
    return sensors


def _result_payload(result) -> dict[str, object]:
    """Convert a script result into a JSON-friendly payload."""
    return {
        "source": result.source,
        "ok": result.ok,
        "passed": result.passed,
        "failed": result.failed,
        "total": len(result.steps),
        "duration_ms": round(result.duration_ms, 1),
        "errors": result.errors,
        "warnings": result.warnings,
        "steps": [
            {"name": s.name, "status": s.status.value, "message": s.message}
            for s in result.steps
        ],
        "variables": result.variables,
    }


def _normalize_target_name(target: str) -> str:
    return target.strip().lower().replace(" ", "-").replace("_", "-")


def _resolve_required_adapter(command: str) -> tuple[str | None, str | None]:
    """Infer the hardware adapter required by a single command, if any."""
    try:
        doc = parse_cql(_build_single_command_scenario(command), "<cmd>")
    except Exception:
        return None, None

    actions = [act for goal in doc.goals for step in goal.steps for act in step.actions]
    if not actions:
        return None, None

    act = actions[0]
    if act.kind == "set" and act.target:
        peripheral = _PERIPHERAL_MAP.get(_normalize_target_name(act.target))
        if peripheral is None:
            return None, act.target
        if peripheral.startswith("pump"):
            return "motor-dri0050", peripheral
        if peripheral.startswith("valve"):
            return "modbus-io", peripheral
        if peripheral.startswith("lung"):
            return "motor-tic249", peripheral
        return None, peripheral

    if act.kind in {"val", "min", "max", "condition", "sample"}:
        return "piadc", act.target or (act.condition.sensor if act.condition else None)

    if act.kind in {"if_block", "if_else"} and act.condition and act.condition.sensor:
        return "piadc", act.condition.sensor

    return None, None


def _preflight_hardware(command: str, firmware_url: str, *, quiet: bool, yaml_output: bool = False) -> bool:
    """Check whether the requested command can run on real hardware."""
    # Try to start firmware if not available
    if not _ensure_firmware_running(firmware_url, quiet=quiet, yaml_output=yaml_output):
        return False

    health = check_firmware_health(firmware_url)
    if "error" in health:
        error_msg = f"Hardware preflight failed: firmware health at {firmware_url} is unavailable ({health['error']})"
        if yaml_output:
            _output_yaml({"status": "error", "message": error_msg}, quiet=quiet)
        else:
            click.echo(f"❌ {error_msg}", err=True)
        return False

    if str(health.get("mode", "")).lower() != "real":
        error_msg = f"Hardware preflight failed: firmware mode is {health.get('mode', 'unknown')!r}; real hardware is required"
        if yaml_output:
            _output_yaml({"status": "error", "message": error_msg}, quiet=quiet)
        else:
            click.echo(f"❌ {error_msg}", err=True)
        return False

    identify = check_firmware_identify(firmware_url)
    if "error" in identify:
        error_msg = f"Hardware preflight failed: hardware identify at {firmware_url} is unavailable ({identify['error']})"
        if yaml_output:
            _output_yaml({"status": "error", "message": error_msg}, quiet=quiet)
        else:
            click.echo(f"❌ {error_msg}", err=True)
        return False

    detected = int(identify.get("detected", 0) or 0)
    total = int(identify.get("total", 0) or 0)
    if detected <= 0:
        total_display = total if total else "?"
        error_msg = f"Hardware preflight failed: no hardware adapters detected ({detected}/{total_display})"
        if yaml_output:
            _output_yaml({"status": "error", "message": error_msg}, quiet=quiet)
        else:
            click.echo(f"❌ {error_msg}", err=True)
        return False

    required_adapter, target = _resolve_required_adapter(command)
    adapter_status = None
    adapters = identify.get("adapters", [])
    if not isinstance(adapters, list):
        adapters = []

    if required_adapter:
        for adapter in adapters:
            if adapter.get("id") == required_adapter:
                adapter_status = adapter.get("status")
                break
        if adapter_status != "ok":
            label = target or required_adapter
            error_msg = f"Hardware preflight failed: {label!r} needs adapter {required_adapter!r} but status is {adapter_status or 'missing'}"
            if yaml_output:
                _output_yaml({"status": "error", "message": error_msg}, quiet=quiet)
            else:
                click.echo(f"❌ {error_msg}", err=True)
            return False

    if not quiet:
        if yaml_output:
            preflight_data = {
                "status": "ok",
                "hardware_preflight": {
                    "url": firmware_url,
                    "mode": health.get("mode", "unknown"),
                    "detected": f"{detected}/{total}",
                    "adapters": adapters,
                },
            }
            if required_adapter:
                preflight_data["hardware_preflight"]["required"] = {
                    "adapter": required_adapter,
                    "status": adapter_status or "missing",
                }
            _output_yaml(preflight_data, quiet=quiet)
        else:
            click.echo("🔎 Hardware preflight")
            click.echo(f"  URL: {firmware_url}")
            click.echo(f"  Mode: {health.get('mode', 'unknown')}")
            click.echo(f"  Detected: {detected}/{total}")
            if required_adapter:
                click.echo(f"  Required: {required_adapter} ({adapter_status or 'missing'})")
            click.echo("  Adapters:")
            for adapter in adapters:
                click.echo(f"    - {adapter.get('id', 'unknown')}: {adapter.get('status', 'unknown')}")

    return True


def _build_single_command_scenario(command: str) -> str:
    """Wrap a single OQL command line in a minimal scenario document."""
    stripped = command.strip()
    if not stripped:
        raise ValueError("Command cannot be empty")

    indented_command = textwrap.indent(stripped, "    ")
    return (
        'SCENARIO: "Single command"\n'
        'GOAL: Execute command\n'
        '  1. Run command:\n'
        f"{indented_command}\n"
    )


def _run_source(source: str, filename: str, *, mode: str, quiet: bool, sensors: dict[str, float], firmware_url: str, skip_waits: bool, bridge_url: str | None = None, yaml_output: bool = False) -> object:
    """Execute a CQL source string with a configured interpreter."""
    interp = CqlInterpreter(
        mode=mode,
        quiet=quiet or yaml_output,  # Suppress text output when using YAML
        sensor_values=sensors,
        firmware_url=firmware_url,
        skip_waits=skip_waits,
        bridge_url=bridge_url,
        yaml_output=yaml_output,
    )
    result = interp.run(source, filename)
    if yaml_output:
        interp.out.output_yaml()
    return result


def _run_single_command(command: str, *, mode: str, quiet: bool, sensors: dict[str, float], firmware_url: str, skip_waits: bool, bridge_url: str | None = None, yaml_output: bool = False) -> object:
    """Execute one OQL command line by wrapping it in a minimal scenario."""
    source = _build_single_command_scenario(command)
    return _run_source(
        source,
        "<cmd>",
        mode=mode,
        quiet=quiet,
        sensors=sensors,
        firmware_url=firmware_url,
        skip_waits=skip_waits,
        bridge_url=bridge_url,
        yaml_output=yaml_output,
    )


def main() -> None:
    argv = sys.argv[1:]
    if argv and argv[0] == "cmd":
        cmd_parser = argparse.ArgumentParser(
            prog="oqlctl cmd",
            description="Execute a single OQL command line against the firmware.",
        )
        cmd_parser.add_argument("command", help="Single OQL command line to execute")
        cmd_parser.add_argument(
            "-m", "--mode",
            choices=["validate", "dry-run", "execute"],
            default="execute",
            help="Execution mode (default: execute)",
        )
        cmd_parser.add_argument("-q", "--quiet", action="store_true", help="Suppress output")
        cmd_parser.add_argument(
            "-s", "--sensor", action="append", default=[],
            help="Mock sensor value: AI01=7.5",
        )
        cmd_parser.add_argument("--yaml", action="store_true", help="Output YAML result")
        cmd_parser.add_argument("--json", action="store_true", help="Output JSON result")
        cmd_parser.add_argument(
            "--firmware-url", default=DEFAULT_FIRMWARE_URL,
            help=f"Firmware simulator URL (default: {DEFAULT_FIRMWARE_URL})",
        )
        cmd_parser.add_argument(
            "--skip-waits", action="store_true",
            help="Skip real-time waits in execute mode",
        )
        cmd_parser.add_argument(
            "--bridge", help="Event Server URL (e.g. ws://localhost:8104/cli)"
        )

        args = cmd_parser.parse_args(argv[1:])
        sensors = _parse_sensor_overrides(args.sensor)
        if args.mode == "execute" and not _preflight_hardware(
            args.command,
            args.firmware_url,
            quiet=args.quiet,
            yaml_output=args.yaml,
        ):
            sys.exit(1)
        result = _run_single_command(
            args.command,
            mode=args.mode,
            quiet=args.quiet,
            sensors=sensors,
            firmware_url=args.firmware_url,
            skip_waits=args.skip_waits,
            bridge_url=args.bridge,
            yaml_output=args.yaml,
        )
        if args.yaml:
            _output_yaml(_result_payload(result), quiet=args.quiet)
        elif args.json:
            print(json.dumps(_result_payload(result), indent=2, ensure_ascii=False))
        if not result.ok:
            sys.exit(1)
        return

    parser = argparse.ArgumentParser(
        prog="oqlctl",
        description="OQL/CQL Interpreter — Operation Query Language CLI",
    )
    parser.add_argument("file", nargs="?", help="CQL/OQL file to process")
    parser.add_argument(
        "-m", "--mode",
        choices=["validate", "dry-run", "execute"],
        default="dry-run",
        help="Execution mode (default: dry-run)",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress output")
    parser.add_argument(
        "-s", "--sensor", action="append", default=[],
        help="Mock sensor value: AI01=7.5",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    parser.add_argument(
        "--firmware-url", default=DEFAULT_FIRMWARE_URL,
        help=f"Firmware simulator URL (default: {DEFAULT_FIRMWARE_URL})",
    )
    parser.add_argument(
        "--skip-waits", action="store_true",
        help="Skip real-time waits in execute mode",
    )
    parser.add_argument(
        "--bridge", help="Event Server URL (e.g. ws://localhost:8104/cli)"
    )
    parser.add_argument("--validate-dir", help="Validate all .cql/.oql files in directory")

    args = parser.parse_args()

    # Parse sensor overrides
    sensors = _parse_sensor_overrides(args.sensor)

    # Validate directory mode
    if args.validate_dir:
        _validate_directory(Path(args.validate_dir))
        return

    if not args.file:
        parser.print_help()
        return

    interp = CqlInterpreter(
        mode=args.mode,
        quiet=args.quiet,
        sensor_values=sensors,
        firmware_url=args.firmware_url,
        skip_waits=args.skip_waits,
        bridge_url=args.bridge,
    )
    result = interp.run_file(args.file)

    if args.json:
        print(json.dumps(_result_payload(result), indent=2, ensure_ascii=False))


def _validate_directory(d: Path) -> None:
    """Validate all .cql and .oql files in a directory tree."""
    files = sorted(list(d.rglob("*.cql")) + list(d.rglob("*.oql")))
    if not files:
        print(f"No .cql/.oql files found in {d}")
        return

    total_issues = 0
    for f in files:
        interp = CqlInterpreter(mode="validate", quiet=True)
        result = interp.run_file(str(f))
        issues = len(result.warnings) + len(result.errors)
        total_issues += issues
        icon = "✅" if issues == 0 else "⚠️ "
        print(f"  {icon} {f.relative_to(d)}: {issues} issue(s)")

    status = "✅" if total_issues == 0 else "⚠️ "
    print(f"\n{status} {len(files)} files, {total_issues} total issues")


if __name__ == "__main__":
    main()
