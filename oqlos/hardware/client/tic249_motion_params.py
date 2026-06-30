from __future__ import annotations

from typing import Any

from oqlos.hardware.client.tic249_arg_helpers import tic249_arg
from oqlos.hardware.client.tic249_rig_direction import apply_rig_direction_to_plugin_params
from oqlos.hardware.tic249_units import (
    TIC249_DEFAULT_LUNG_PAUSE_SECONDS,
    TIC249_DEFAULT_STEPS_PER_SECOND,
    TIC249_DEFAULT_TARGET_VELOCITY,
    steps_per_second_to_raw,
)

_MOTION_META_KEYS = (
    "speed_unit",
    "speedUnit",
    "max_steps_per_second",
    "maxStepsPerSecond",
    "acceleration_unit",
    "accelerationUnit",
    "accelerationPercentPerSecond",
    "default_speed_steps_per_second",
    "defaultSpeedStepsPerSecond",
)


def normalize_motion_params(args: dict[str, Any]) -> dict[str, Any]:
    params = dict(args)
    speed_unit = tic249_arg(params, "speed_unit", "speedUnit")
    if "speed" in params and speed_unit == "steps/s":
        params["speed"] = steps_per_second_to_raw(
            params["speed"],
            max_steps_per_second=tic249_arg(params, "max_steps_per_second", "maxStepsPerSecond"),
        )
    elif "speed" in params and tic249_arg(params, "max_steps_per_second", "maxStepsPerSecond") is not None:
        params["speed"] = steps_per_second_to_raw(
            params["speed"],
            max_steps_per_second=tic249_arg(params, "max_steps_per_second", "maxStepsPerSecond"),
        )

    acceleration_unit = tic249_arg(params, "acceleration_unit", "accelerationUnit")
    acceleration = tic249_arg(params, "acceleration", "accelerationPercentPerSecond")
    if acceleration is not None:
        try:
            value = float(acceleration)
        except (TypeError, ValueError):
            value = 0.0
        if "accelerationPercentPerSecond" in params and value > 100:
            value = 100
        if acceleration_unit in {"%/s", "percent/s", "percent_per_second"}:
            params["acceleration"] = int(value * 1000)
        elif acceleration_unit in {"pulses/s2", "steps/s2", "steps/s^2"}:
            params["acceleration"] = int(value * 100)
        elif "accelerationPercentPerSecond" in params:
            params["acceleration"] = int(value * 1000)

    for key in _MOTION_META_KEYS:
        params.pop(key, None)
    return params


def stroke_steps(args: dict[str, Any], default: int = 500) -> int:
    return int(tic249_arg(args, "steps", "strokeSteps", tic249_arg(args, "stroke_steps", "strokeSteps", default)))


def apply_reciprocate_direction(params: dict[str, Any], args: dict[str, Any]) -> None:
    apply_rig_direction_to_plugin_params(params, args)


def _resolve_reciprocate_speed(args: dict[str, Any]) -> int | None:
    speed = tic249_arg(args, "speed", None, TIC249_DEFAULT_STEPS_PER_SECOND)
    if speed is None:
        return None
    if tic249_arg(args, "speed_unit", "speedUnit") == "steps/s" or "speed_unit" in args or "speedUnit" in args:
        return steps_per_second_to_raw(
            speed,
            max_steps_per_second=tic249_arg(args, "max_steps_per_second", "maxStepsPerSecond"),
            default_steps_per_second=float(TIC249_DEFAULT_TARGET_VELOCITY / 10_000),
        )
    return int(speed)


def _resolve_reciprocate_ramp(args: dict[str, Any]) -> float | None:
    ramp_time = tic249_arg(args, "ramp_seconds", "rampSeconds")
    if ramp_time is None:
        ramp_time = tic249_arg(args, "ramp_time_sec", "rampTimeSec")
    if ramp_time is None:
        ramp_time = tic249_arg(args, "ramp_time", "rampTime")
    if ramp_time is None:
        return None
    return float(ramp_time)


def build_reciprocate_params(args: dict[str, Any], *, default_cycles: int) -> dict[str, Any]:
    """Build plugin ``reciprocate`` params; preserve limit_mode for physical end switches."""
    pause_raw = tic249_arg(args, "pause")
    if pause_raw is None:
        pause_raw = tic249_arg(args, "tick_seconds", "tickSeconds", 0.0)
    params: dict[str, Any] = {
        "steps": stroke_steps(args),
        "cycles": int(args.get("cycles", default_cycles)),
        "pause": float(pause_raw or 0.0),
    }
    speed = _resolve_reciprocate_speed(args)
    if speed is not None:
        params["speed"] = speed

    apply_reciprocate_direction(params, args)

    limit_mode = tic249_arg(args, "limit_mode", "limitMode")
    if limit_mode is not None:
        params["limit_mode"] = str(limit_mode)

    if tic249_arg(args, "acceleration", "accelerationPercentPerSecond") is not None:
        normalized = normalize_motion_params(
            {
                "acceleration": tic249_arg(args, "acceleration", "accelerationPercentPerSecond"),
                "acceleration_unit": tic249_arg(args, "acceleration_unit", "accelerationUnit"),
            }
        )
        if normalized.get("acceleration") is not None:
            params["acceleration"] = normalized["acceleration"]

    ramp_time = _resolve_reciprocate_ramp(args)
    if ramp_time is not None:
        params["ramp_seconds"] = ramp_time

    return params
