"""
Utility functions for CQL CLI.

Low-complexity helper functions extracted from the monolithic cql_cli.py
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import yaml

from oqlos.core.cql_parser import parse_cql
from oqlos.hardware.firmware_adapter import _PERIPHERAL_MAP


def output_yaml(data: dict, quiet: bool = False) -> None:
    """Output data as YAML to stdout."""
    if not quiet:
        print(yaml.dump(data, default_flow_style=False, sort_keys=False), end="")


def parse_sensor_overrides(sensor_args: list[str]) -> dict[str, float]:
    """Parse `-s name=value` overrides into a sensor mapping."""
    sensors: dict[str, float] = {}
    for s in sensor_args:
        if "=" not in s:
            continue
        key, value = s.split("=", 1)
        sensors[key.strip()] = float(value.strip())
    return sensors


def build_result_payload(result) -> dict[str, object]:
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


def normalize_target_name(target: str) -> str:
    """Normalize a target name for consistent lookup."""
    return target.strip().lower().replace(" ", "-").replace("_", "-")


def build_single_command_scenario(command: str) -> str:
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


def resolve_required_adapter(command: str) -> tuple[str | None, str | None]:
    """Infer the hardware adapter required by a single command, if any."""
    try:
        doc = parse_cql(build_single_command_scenario(command), "<cmd>")
    except Exception:
        return None, None

    actions = [act for goal in doc.goals for step in goal.steps for act in step.actions]
    if not actions:
        return None, None

    act = actions[0]
    if act.kind == "set" and act.target:
        peripheral = _PERIPHERAL_MAP.get(normalize_target_name(act.target))
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


def validate_directory(d: Path, interpreter_class) -> None:
    """Validate all .cql and .oql files in a directory tree."""
    files = sorted(list(d.rglob("*.cql")) + list(d.rglob("*.oql")))
    if not files:
        print(f"No .cql/.oql files found in {d}")
        return

    total_issues = 0
    for f in files:
        interp = interpreter_class(mode="validate", quiet=True)
        result = interp.run_file(str(f))
        issues = len(result.warnings) + len(result.errors)
        total_issues += issues
        icon = "[OK]" if issues == 0 else "[WARN]"
        print(f"  {icon} {f.relative_to(d)}: {issues} issue(s)")

    status = "[OK]" if total_issues == 0 else "[WARN]"
    print(f"\n{status} {len(files)} files, {total_issues} total issues")
