"""OqlOS-owned hardware MAP contract used by the moved hardware UI."""

from __future__ import annotations

from typing import Any

from oqlos.api.hardware_mapping_motor2 import validate_motor2_config

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


def _validate_motor2(motor2_raw: Any, issues: list[str]) -> None:
    validate_motor2_config(motor2_raw, issues)


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
