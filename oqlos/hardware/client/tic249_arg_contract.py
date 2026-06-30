"""Tic249 runtime argument contract helpers for OqlOS clients."""

from __future__ import annotations

from typing import Any

MOTOR2_RUNTIME_ALIASES = {"motor2", "motor-tic249", "motor_tic249", "tic249"}

_CANONICAL_KEYS = {
    "peripheral_id": "peripheralId",
    "peripheralid": "peripheralId",
    "stroke_steps": "strokeSteps",
    "strokesteps": "strokeSteps",
    "cycle_volume_liters": "cycleVolumeLiters",
    "cyclevolumeliters": "cycleVolumeLiters",
    "max_steps_per_second": "maxStepsPerSecond",
    "maxstepspersecond": "maxStepsPerSecond",
    "default_speed_steps_per_second": "defaultSpeedStepsPerSecond",
    "defaultspeedstepspersecond": "defaultSpeedStepsPerSecond",
    "speed_unit": "speedUnit",
    "speedunit": "speedUnit",
    "acceleration_percent_per_second": "accelerationPercentPerSecond",
    "accelerationpercentpersecond": "accelerationPercentPerSecond",
    "acceleration_unit": "accelerationUnit",
    "accelerationunit": "accelerationUnit",
    "limit_mode": "limitMode",
    "limitmode": "limitMode",
    "start_direction": "startDirection",
    "startdirection": "startDirection",
}


def canonicalize_motor2_runtime_key(key: str) -> str:
    token = str(key or "").strip()
    return _CANONICAL_KEYS.get(token.replace("-", "_").lower(), token)


def tic249_runtime_args_from_config(runtime_config: dict[str, Any]) -> dict[str, Any]:
    source = runtime_config.get("motor2")
    if not isinstance(source, dict):
        for alias in MOTOR2_RUNTIME_ALIASES:
            candidate = runtime_config.get(alias)
            if isinstance(candidate, dict):
                source = candidate
                break
    if not isinstance(source, dict):
        return {}

    canonical = {canonicalize_motor2_runtime_key(k): v for k, v in source.items()}
    out: dict[str, Any] = {}
    mapping = {
        "maxStepsPerSecond": "max_steps_per_second",
        "defaultSpeedStepsPerSecond": "default_speed_steps_per_second",
        "speedUnit": "speed_unit",
        "strokeSteps": "steps",
        "cycleVolumeLiters": "cycle_volume_liters",
        "accelerationPercentPerSecond": "acceleration",
        "accelerationUnit": "acceleration_unit",
        "limitMode": "limit_mode",
        "startDirection": "start_direction",
    }
    for src_key, dst_key in mapping.items():
        if src_key in canonical:
            out[dst_key] = canonical[src_key]
    return out
