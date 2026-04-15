"""
CQL CLI entry point — run, validate, and batch-check .cql/.oql scenario files.

Usage:
  oqlctl file.cql
  oqlctl file.cql --mode validate
  oqlctl --validate-dir scenarios/
  python -m oqlos.tools.cql_cli file.oql --mode dry-run
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from oqlos.core.interpreter import CqlInterpreter


def main() -> None:
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
        "--firmware-url", default="http://localhost:8202",
        help="Firmware simulator URL (default: http://localhost:8202)",
    )
    parser.add_argument(
        "--skip-waits", action="store_true",
        help="Skip real-time waits in execute mode",
    )
    parser.add_argument("--validate-dir", help="Validate all .cql/.oql files in directory")

    args = parser.parse_args()

    # Parse sensor overrides
    sensors: dict[str, float] = {}
    for s in args.sensor:
        if "=" in s:
            k, v = s.split("=", 1)
            sensors[k.strip()] = float(v.strip())

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
    )
    result = interp.run_file(args.file)

    if args.json:
        print(json.dumps({
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
        }, indent=2, ensure_ascii=False))


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
