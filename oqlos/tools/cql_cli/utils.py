"""
Utility functions for the OQL CLI (legacy module path).

Low-complexity helper functions extracted from the monolithic cql_cli.py
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import yaml

from oqlos.core.cql_parser import parse_cql
from oqlos.hardware.firmware_adapter import _PERIPHERAL_MAP

_PERIPHERAL_ADAPTERS = {
    "pump": "motor-dri0050",
    "valve": "modbus-io",
    "lung": "motor-tic249",
}
_SENSOR_ADAPTER = "modbus-adc"

_SENSOR_ACTION_KINDS = {"val", "min", "max", "condition", "sample"}


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

    indented_command = textwrap.indent(stripped, "  ")
    return (
        "VERSION: 4\n"
        "SCENARIO: Single command\n"
        "GOAL:\n"
        "  SET NAME 'Execute command'\n"
        f"{indented_command}\n"
    )


def _extract_first_action(command: str):
    """Parse a one-line command and return its first action, if any."""
    try:
        doc = parse_cql(build_single_command_scenario(command), "<cmd>")
    except Exception:
        return None

    for goal in doc.goals:
        for step in goal.steps:
            for action in step.actions:
                return action
    return None


def _resolve_peripheral_adapter(target: str) -> tuple[str | None, str | None]:
    """Map a normalized peripheral target to the adapter it requires."""
    peripheral = _PERIPHERAL_MAP.get(normalize_target_name(target))
    if peripheral is None:
        return None, target

    for prefix, adapter_id in _PERIPHERAL_ADAPTERS.items():
        if peripheral.startswith(prefix):
            return adapter_id, peripheral
    return None, peripheral


def _resolve_sensor_target(action) -> str | None:
    """Resolve the sensor name carried by a scalar or condition action."""
    return action.target or (action.condition.sensor if action.condition else None)


def resolve_required_adapter(command: str) -> tuple[str | None, str | None]:
    """Infer the hardware adapter required by a single command, if any."""
    action = _extract_first_action(command)
    if action is None:
        return None, None

    if action.kind == "set" and action.target:
        return _resolve_peripheral_adapter(action.target)

    if action.kind in _SENSOR_ACTION_KINDS:
        return _SENSOR_ADAPTER, _resolve_sensor_target(action)

    if action.kind in {"if_block", "if_else"} and action.condition and action.condition.sensor:
        return _SENSOR_ADAPTER, action.condition.sensor

    return None, None


def validate_directory(d: Path, interpreter_class) -> None:
    """Validate all canonical .oql files in a directory tree."""
    files = sorted(d.rglob("*.oql"))
    if not files:
        print(f"No .oql files found in {d}")
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
