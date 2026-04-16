"""
Command execution helpers for CQL CLI.

Functions for running CQL commands and scenarios.
"""

from __future__ import annotations

import json
import sys
import signal
import asyncio
import time
from pathlib import Path

import click

from oqlos.core.interpreter import CqlInterpreter
from oqlos.tools.cql_cli.utils import build_single_command_scenario, build_result_payload, output_yaml
from oqlos.tools.cql_cli.preflight import preflight_hardware
from oqlos.tools.hardware_diagnose.health import check_firmware_identify


DEFAULT_FIRMWARE_URL = "http://localhost:8202"


def run_source(
    source: str,
    filename: str,
    *,
    mode: str,
    quiet: bool,
    sensors: dict[str, float],
    firmware_url: str,
    skip_waits: bool,
    bridge_url: str | None = None,
    yaml_output: bool = False
) -> object:
    """Execute a CQL source string with a configured interpreter."""
    interp = CqlInterpreter(
        mode=mode,
        quiet=quiet,
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


def run_single_command(
    command: str,
    *,
    mode: str,
    quiet: bool,
    sensors: dict[str, float],
    firmware_url: str,
    skip_waits: bool,
    bridge_url: str | None = None,
    yaml_output: bool = False
) -> object:
    """Execute one OQL command line by wrapping it in a minimal scenario."""
    source = build_single_command_scenario(command)
    return run_source(
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


def handle_list_command(argv: list[str]) -> None:
    """Handle the 'cmd list' subcommand."""
    firmware_url = DEFAULT_FIRMWARE_URL
    yaml_output = "--yaml" in argv

    # Parse optional --firmware-url flag
    if "--firmware-url" in argv:
        idx = argv.index("--firmware-url")
        if idx + 1 < len(argv):
            firmware_url = argv[idx + 1]

    # Get hardware list
    try:
        identify = check_firmware_identify(firmware_url)
        if "error" in identify:
            print(f"Error: {identify['error']}", file=sys.stderr)
            sys.exit(1)

        if yaml_output:
            output_yaml(identify, quiet=False)
        else:
            print(f"Connected devices at {firmware_url}:")
            print(f"  Detected: {identify.get('detected', 0)}/{identify.get('total', 0)}")
            print("  Adapters:")
            for adapter in identify.get("adapters", []):
                print(f"    - {adapter.get('id', 'unknown')}: {adapter.get('status', 'unknown')}")
                print(f"      Name: {adapter.get('name', 'N/A')}")
                print(f"      Description: {adapter.get('description', 'N/A')}")
    except Exception as exc:
        print(f"Error listing devices: {exc}", file=sys.stderr)
        sys.exit(1)


def execute_command_with_cleanup(
    args,
    result,
    yaml_output: bool,
    quiet: bool
) -> None:
    """Execute command with continuous mode and cleanup handling."""
    continuous = args.continuous and not args.once

    if yaml_output:
        output_yaml(build_result_payload(result), quiet=args.quiet)
    elif args.json:
        print(json.dumps(build_result_payload(result), indent=2, ensure_ascii=False))

    # Continuous mode: keep running until Ctrl+C
    if continuous and result.ok and args.mode == "execute":
        _run_continuous_mode(args, quiet)

    if not result.ok:
        sys.exit(1)


def _run_continuous_mode(args, quiet: bool) -> None:
    """Run in continuous mode with cleanup on interrupt."""
    from oqlos.hardware.plugin_gateway import PluginHardwareGateway

    async def run_cleanup():
        """Async cleanup function."""
        gateway = PluginHardwareGateway(mode="real")
        await gateway._initialize_plugins()

        if not quiet:
            print("\nShutting down...", file=sys.stderr)
        try:
            # Stop pump
            pump_result = await gateway.set_pump(0)
            if not quiet:
                print(f"Pump stopped: {pump_result.get('success', False)}", file=sys.stderr)
            # Close valves if needed
            if "valve" in args.command.lower() or "zawór" in args.command.lower():
                await gateway.set_valve("valve-1", False)
                await gateway.set_valve("valve-2", False)
                if not quiet:
                    print("Valves closed", file=sys.stderr)
            if not quiet:
                print("Hardware stopped", file=sys.stderr)
        except Exception as exc:
            if not quiet:
                print(f"Cleanup error: {exc}", file=sys.stderr)
        finally:
            sys.exit(0)

    def cleanup(signum=None, frame=None):
        """Cleanup hardware on interrupt."""
        asyncio.run(run_cleanup())

    signal.signal(signal.SIGINT, cleanup)

    try:
        if not quiet:
            print("Press Ctrl+C to stop...", file=sys.stderr)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()
