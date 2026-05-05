"""
CQL CLI main entry point.

Refactored from monolithic cql_cli.py (CC=26, 533L) into focused functions.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from oqlos.core.interpreter import CqlInterpreter
from oqlos.tools.cql_cli.utils import (
    parse_sensor_overrides,
    validate_directory,
)
from oqlos.tools.cql_cli.commands import (
    DEFAULT_FIRMWARE_URL,
    handle_list_command,
    run_single_command,
    execute_command_with_cleanup,
)
from oqlos.tools.cql_cli.preflight import preflight_hardware


def create_file_parser() -> argparse.ArgumentParser:
    """Create argument parser for file-based execution."""
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
    parser.add_argument("--status", action="store_true", help="Show hardware health status")
    parser.add_argument("--identify", action="store_true", help="Show hardware identification")
    parser.add_argument("--detect", action="store_true", help="Run smart local hardware detection")
    parser.add_argument("--doctor", action="store_true", help="Diagnose OqlOS hardware config/runtime issues")
    parser.add_argument("--fix", action="store_true", help="Apply safe doctor repairs")
    parser.add_argument("--config", help="Path to oqlos.yaml for detect/doctor")
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
    return parser


def create_hardware_parser(action: str) -> argparse.ArgumentParser:
    """Create parser for oqlctl hardware utility subcommands."""
    parser = argparse.ArgumentParser(
        prog=f"oqlctl {action}",
        description=f"OqlOS hardware {action}",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    parser.add_argument(
        "--firmware-url", default=DEFAULT_FIRMWARE_URL,
        help=f"Firmware simulator URL (default: {DEFAULT_FIRMWARE_URL})",
    )
    parser.add_argument("--config", help="Path to oqlos.yaml (default: auto-detect)")
    if action == "doctor":
        parser.add_argument("--fix", action="store_true", help="Apply safe doctor repairs")
    return parser


def create_cmd_parser() -> argparse.ArgumentParser:
    """Create argument parser for single command execution."""
    parser = argparse.ArgumentParser(
        prog="oqlctl cmd",
        description="Execute a single OQL command line against the firmware.",
    )
    parser.add_argument("command", help="Single OQL command line to execute")
    parser.add_argument(
        "-m", "--mode",
        choices=["validate", "dry-run", "execute"],
        default="execute",
        help="Execution mode (default: execute)",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress output")
    parser.add_argument(
        "-s", "--sensor", action="append", default=[],
        help="Mock sensor value: AI01=7.5",
    )
    parser.add_argument("--yaml", action="store_true", default=True, help="Output YAML result (default: true)")
    parser.add_argument("--text", action="store_true", help="Output text result with emojis (default: false)")
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
        "--continuous", "-c", action="store_true",
        help="Keep command active until Ctrl+C"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Execute command once and exit"
    )
    parser.add_argument(
        "--bridge", help="Event Server URL (e.g. ws://localhost:8104/cli)"
    )
    return parser


def run_file_mode(args: argparse.Namespace) -> None:
    """Execute file-based CQL/OQL processing."""
    if _run_hardware_flags(args):
        return

    # Parse sensor overrides
    sensors = parse_sensor_overrides(args.sensor)

    # Validate directory mode
    if args.validate_dir:
        validate_directory(Path(args.validate_dir), CqlInterpreter)
        return

    if not args.file:
        # Create parser just for help
        create_file_parser().print_help()
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
        from oqlos.tools.cql_cli.utils import build_result_payload
        import json
        print(json.dumps(build_result_payload(result), indent=2, ensure_ascii=False))


def _run_hardware_flags(args: argparse.Namespace) -> bool:
    """Handle hardware utility flags on the file-mode parser."""
    if args.status:
        from oqlos.tools.hardware_diagnose.health import cmd_health
        print(cmd_health(args.firmware_url))
        return True

    if args.identify:
        from oqlos.tools.hardware_diagnose.health import check_firmware_identify
        import json

        data = check_firmware_identify(args.firmware_url)
        print(json.dumps(data) if args.json else json.dumps(data, indent=2, default=str))
        return True

    if args.detect:
        from oqlos.tools.hardware_diagnose.doctor import detect_hardware, format_detection
        import json

        data = detect_hardware(args.firmware_url, config_path=args.config)
        print(json.dumps(data) if args.json else format_detection(data))
        return True

    if args.doctor or args.fix:
        from oqlos.tools.hardware_diagnose.doctor import build_doctor_report, format_doctor
        import json

        data = build_doctor_report(args.firmware_url, config_path=args.config, fix=args.fix)
        print(json.dumps(data) if args.json else format_doctor(data))
        return True

    return False


def run_hardware_mode(action: str, argv: list[str]) -> None:
    """Run oqlctl status/identify/detect/doctor subcommands."""
    args = create_hardware_parser(action).parse_args(argv)
    from types import SimpleNamespace

    _run_hardware_flags(SimpleNamespace(
        status=action == "status",
        identify=action == "identify",
        detect=action == "detect",
        doctor=action == "doctor",
        fix=getattr(args, "fix", False),
        json=args.json,
        firmware_url=args.firmware_url,
        config=args.config,
    ))


def run_cmd_mode(argv: list[str]) -> None:
    """Execute single command mode."""
    args = create_cmd_parser().parse_args(argv)
    sensors = parse_sensor_overrides(args.sensor)

    # YAML is default, unless --text is specified
    yaml_output = not args.text
    args.yaml = yaml_output  # Update args for consistency

    if args.mode == "execute" and not preflight_hardware(
        args.command,
        args.firmware_url,
        quiet=args.quiet,
        yaml_output=yaml_output,
    ):
        sys.exit(1)

    result = run_single_command(
        args.command,
        mode=args.mode,
        quiet=args.quiet,
        sensors=sensors,
        firmware_url=args.firmware_url,
        skip_waits=args.skip_waits,
        bridge_url=args.bridge,
        yaml_output=yaml_output,
    )

    execute_command_with_cleanup(args, result, yaml_output, args.quiet)


def _dispatch_to_mode(argv: list[str]) -> None:
    """Dispatch to appropriate CLI mode based on arguments."""
    # Empty args - show help
    if not argv:
        create_file_parser().print_help()
        return

    # Not cmd mode - file mode
    if argv[0] in {"status", "identify", "detect", "doctor"}:
        run_hardware_mode(argv[0], argv[1:])
        return

    # Not cmd mode - file mode
    if argv[0] != "cmd":
        args = create_file_parser().parse_args(argv)
        run_file_mode(args)
        return

    # cmd mode - check for list subcommand
    if len(argv) >= 2 and argv[1] == "list":
        handle_list_command(argv)
        return

    # Standard cmd mode
    run_cmd_mode(argv[1:])


def main() -> None:
    """Main entry point - delegates to dispatcher."""
    argv = sys.argv[1:]
    _dispatch_to_mode(argv)


if __name__ == "__main__":
    main()
