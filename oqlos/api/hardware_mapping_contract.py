"""OqlOS-owned hardware MAP contract used by the moved hardware UI."""

from __future__ import annotations

from typing import Any

from oqlos.hardware.client.tic249_arg_contract import canonicalize_motor2_runtime_key

MAPPING_CONTRACT_VERSION = "hardware-map-v1"

MAP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "runtimeConfig": {
            "type": "object",
            "properties": {
                "motor2": {
                    "type": "object",
                    "properties": {
                        "peripheralId": {"type": "string", "minLength": 1},
                        "strokeSteps": {"type": "integer", "minimum": 1},
                        "cycleVolumeLiters": {"type": "number", "minimum": 0},
                        "maxStepsPerSecond": {"type": "integer", "minimum": 1},
                        "defaultSpeedStepsPerSecond": {"type": "integer", "minimum": 1},
                        "speedUnit": {"type": "string"},
                        "accelerationPercentPerSecond": {"type": "number", "minimum": 0},
                        "accelerationUnit": {"type": "string"},
                        "limitMode": {"type": "string"},
                        "startDirection": {"type": "string"},
                    },
                }
            },
        },
        "objectActionMap": {"type": "object"},
        "paramSensorMap": {"type": "object"},
        "actions": {"type": "object"},
        "funcImplementations": {"type": "object"},
    },
}


class MappingContractError(ValueError):
    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        super().__init__("; ".join(issues))


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_motor2(motor2_raw: Any, issues: list[str]) -> None:
    if not isinstance(motor2_raw, dict):
        if motor2_raw is not None:
            issues.append("runtimeConfig.motor2 must be an object")
        return

    motor2 = {canonicalize_motor2_runtime_key(k): v for k, v in motor2_raw.items()}
    peripheral_id = motor2.get("peripheralId")
    if peripheral_id is not None and (not isinstance(peripheral_id, str) or not peripheral_id.strip()):
        issues.append("runtimeConfig.motor2.peripheralId must be a non-empty string")

    stroke_steps = motor2.get("strokeSteps")
    if stroke_steps is not None and (not _is_int(stroke_steps) or stroke_steps < 1):
        issues.append("runtimeConfig.motor2.strokeSteps must be an integer >= 1")

    max_speed = motor2.get("maxStepsPerSecond")
    if max_speed is not None and (not _is_int(max_speed) or max_speed < 1):
        issues.append("runtimeConfig.motor2.maxStepsPerSecond must be an integer >= 1")

    default_speed = motor2.get("defaultSpeedStepsPerSecond")
    if default_speed is not None and (not _is_int(default_speed) or default_speed < 1):
        issues.append("runtimeConfig.motor2.defaultSpeedStepsPerSecond must be an integer >= 1")
    if _is_int(default_speed) and _is_int(max_speed) and default_speed > max_speed:
        issues.append("runtimeConfig.motor2.defaultSpeedStepsPerSecond must be <= maxStepsPerSecond")


def validate_mapping_contract(mapping: dict[str, Any]) -> None:
    issues: list[str] = []
    for section in ("runtimeConfig", "objectActionMap", "paramSensorMap", "actions", "funcImplementations"):
        value = mapping.get(section)
        if value is not None and not isinstance(value, dict):
            issues.append(f"{section} must be an object")

    runtime = mapping.get("runtimeConfig") if isinstance(mapping.get("runtimeConfig"), dict) else {}
    _validate_motor2(runtime.get("motor2"), issues)

    if issues:
        raise MappingContractError(issues)
