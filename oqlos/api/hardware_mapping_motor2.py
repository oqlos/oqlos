"""Motor2 runtimeConfig validation helpers for hardware MAP contract."""

from __future__ import annotations

from typing import Any

from oqlos.hardware.client.tic249_arg_contract import canonicalize_motor2_runtime_key


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _append_peripheral_id_issue(motor2: dict[str, Any], issues: list[str]) -> None:
    peripheral_id = motor2.get("peripheralId")
    if peripheral_id is not None and (not isinstance(peripheral_id, str) or not peripheral_id.strip()):
        issues.append("runtimeConfig.motor2.peripheralId must be a non-empty string")


def _append_stroke_steps_issue(motor2: dict[str, Any], issues: list[str]) -> None:
    stroke_steps = motor2.get("strokeSteps")
    if stroke_steps is not None and (not _is_int(stroke_steps) or stroke_steps < 1):
        issues.append("runtimeConfig.motor2.strokeSteps must be an integer >= 1")


def _append_speed_issues(motor2: dict[str, Any], issues: list[str]) -> None:
    max_speed = motor2.get("maxStepsPerSecond")
    if max_speed is not None and (not _is_int(max_speed) or max_speed < 1):
        issues.append("runtimeConfig.motor2.maxStepsPerSecond must be an integer >= 1")

    default_speed = motor2.get("defaultSpeedStepsPerSecond")
    if default_speed is not None and (not _is_int(default_speed) or default_speed < 1):
        issues.append("runtimeConfig.motor2.defaultSpeedStepsPerSecond must be an integer >= 1")
    if _is_int(default_speed) and _is_int(max_speed) and default_speed > max_speed:
        issues.append("runtimeConfig.motor2.defaultSpeedStepsPerSecond must be <= maxStepsPerSecond")


def validate_motor2_config(motor2_raw: Any, issues: list[str]) -> None:
    """Validate runtimeConfig.motor2 fields; append human-readable issues."""
    if not isinstance(motor2_raw, dict):
        if motor2_raw is not None:
            issues.append("runtimeConfig.motor2 must be an object")
        return

    motor2 = {canonicalize_motor2_runtime_key(k): v for k, v in motor2_raw.items()}
    _append_peripheral_id_issue(motor2, issues)
    _append_stroke_steps_issue(motor2, issues)
    _append_speed_issues(motor2, issues)
