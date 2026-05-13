"""
CQL CLI main entry point.

Refactored from monolithic cql_cli.py (CC=26, 533L) into focused functions.
"""

from __future__ import annotations

import argparse
import json
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
from oqlos.tools.cql_cli.formatting import canonicalize_oql_text
from oqlos.tools.cql_cli.preflight import preflight_hardware


class ScenarioFetchError(RuntimeError):
    """Raised when an HTTP scenario target is not runnable OQL/CQL source."""


def create_file_parser(
    *,
    prog: str = "oqlctl",
    description: str = "OQL/CQL Interpreter — Operation Query Language CLI",
    file_help: str = "CQL/OQL file to process",
) -> argparse.ArgumentParser:
    """Create argument parser for file-based execution."""
    parser = argparse.ArgumentParser(
        prog=prog,
        description=description,
    )
    parser.add_argument("file", nargs="?", help=file_help)
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


def create_run_parser() -> argparse.ArgumentParser:
    """Create parser for explicit `oqlctl run` scenario execution."""
    return create_file_parser(
        prog="oqlctl run",
        description="Run an OQL/CQL scenario from a file or URL",
        file_help="CQL/OQL file or URL to process",
    )


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


def create_format_parser() -> argparse.ArgumentParser:
    """Create parser for `oqlctl format`."""
    parser = argparse.ArgumentParser(
        prog="oqlctl format",
        description="Format an OQL/CQL file to canonical OQL syntax.",
    )
    parser.add_argument("file", help="CQL/OQL file to format")
    parser.add_argument("--write", "-w", action="store_true", help="Write changes back to the file")
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

    interp = _create_interpreter(args, sensors)
    try:
        result = _run_interpreter_target(interp, args.file)
    except ScenarioFetchError as exc:
        _print_cli_error(str(exc), json_output=args.json)
        sys.exit(1)

    if args.json:
        from oqlos.tools.cql_cli.utils import build_result_payload
        print(json.dumps(build_result_payload(result), indent=2, ensure_ascii=False))


def _create_interpreter(args: argparse.Namespace, sensors: dict[str, float]) -> CqlInterpreter:
    return CqlInterpreter(
        mode=args.mode,
        quiet=args.quiet,
        sensor_values=sensors,
        firmware_url=args.firmware_url,
        skip_waits=args.skip_waits,
        bridge_url=args.bridge,
    )


def _run_interpreter_target(interp: CqlInterpreter, target: str):
    """Run a local file or HTTP(S) scenario target."""
    if target.startswith(("http://", "https://")):
        source = _fetch_scenario_source(target)
        return interp.run(source, target)
    return interp.run_file(target)


def _fetch_scenario_source(url: str) -> str:
    """Fetch OQL/CQL source from raw text or JSON scenario endpoints."""
    import httpx

    try:
        response = httpx.get(url, timeout=20.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ScenarioFetchError(f"Cannot fetch scenario URL {url}: {exc}") from exc

    text = response.text
    content_type = response.headers.get("content-type", "")
    if "json" not in content_type.lower():
        if _looks_like_html(text, content_type):
            raise ScenarioFetchError(
                f"URL returned HTML, not OQL/CQL source: {url}. "
                "Use an API endpoint that returns raw OQL/CQL or JSON with "
                "code/dsl/source/content, or run an exported .oql file."
            )
        if not text.strip():
            raise ScenarioFetchError(f"URL returned an empty scenario response: {url}")
        return text

    try:
        data = response.json()
    except ValueError as exc:
        raise ScenarioFetchError(f"URL returned invalid JSON: {url}") from exc

    source = _extract_scenario_source(data)
    if source:
        return source
    raise ScenarioFetchError(f"URL did not return OQL/CQL source: {url}")


def _extract_scenario_source(data: object) -> str | None:
    """Extract OQL/CQL source from supported JSON response shapes."""
    if not isinstance(data, dict):
        return None

    for key in ("code", "dsl", "source", "content"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value

    scenario = data.get("scenario")
    if isinstance(scenario, dict):
        for key in ("code", "dsl", "source", "content"):
            value = scenario.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return None


def _looks_like_html(text: str, content_type: str) -> bool:
    """Detect editor/SPA pages accidentally passed as scenario source URLs."""
    if "html" in content_type.lower():
        return True
    prefix = text.lstrip()[:128].lower()
    return prefix.startswith("<!doctype html") or prefix.startswith("<html")


def _print_cli_error(message: str, *, json_output: bool = False) -> None:
    if json_output:
        print(json.dumps({"status": "error", "message": message}, ensure_ascii=False))
        return
    print(f"status: error\nmessage: {message}")


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

    # YAML is default, unless --text or --json is specified.
    yaml_output = not args.text and not args.json
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


def run_format_mode(argv: list[str]) -> None:
    """Format a local OQL/CQL file."""
    args = create_format_parser().parse_args(argv)
    path = Path(args.file)
    source = path.read_text(encoding="utf-8")
    formatted = canonicalize_oql_text(source)
    if args.write:
        path.write_text(formatted, encoding="utf-8")
        return
    print(formatted, end="")


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

    if argv[0] == "run":
        args = create_run_parser().parse_args(argv[1:])
        run_file_mode(args)
        return

    if argv[0] == "format":
        run_format_mode(argv[1:])
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
