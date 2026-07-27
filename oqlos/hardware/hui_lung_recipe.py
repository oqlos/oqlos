"""HUI artificial-lung reciprocate recipe (Tic249-backed)."""

from __future__ import annotations

from typing import Any

from oqlos.hardware.tic249_units import (
    TIC249_DEFAULT_LUNG_PAUSE_SECONDS,
    TIC249_DEFAULT_LUNG_RAMP_SECONDS,
    raw_acceleration_for_ramp,
    steps_per_second_to_raw,
)

HUI_AL_LUNG_VALVE_ID = "valve-4"
HUI_LUNG_STROKE_STEPS = 1_000_000
HUI_LUNG_MAX_SPEED_STEPS_PER_S = 10_000
HUI_LUNG_PAUSE_SECONDS = TIC249_DEFAULT_LUNG_PAUSE_SECONDS
HUI_LUNG_RAMP_SECONDS = TIC249_DEFAULT_LUNG_RAMP_SECONDS
HUI_LUNG_DEFAULT_CYCLES = 1_000_000


def build_hui_lung_reciprocate_args() -> dict[str, Any]:
    """Canonical HUI AL reciprocate payload for motor-tic249 / sidecar."""
    raw_speed = steps_per_second_to_raw(
        HUI_LUNG_MAX_SPEED_STEPS_PER_S,
        max_steps_per_second=HUI_LUNG_MAX_SPEED_STEPS_PER_S,
    )
    return {
        "direction": "right",
        "start_direction": "right",
        "limit_mode": "reverse_on_limit",
        "steps": HUI_LUNG_STROKE_STEPS,
        "stroke_steps": HUI_LUNG_STROKE_STEPS,
        "speed": raw_speed,
        "cycles": HUI_LUNG_DEFAULT_CYCLES,
        "pause": HUI_LUNG_PAUSE_SECONDS,
        "ramp_seconds": HUI_LUNG_RAMP_SECONDS,
        "acceleration": raw_acceleration_for_ramp(raw_speed, HUI_LUNG_RAMP_SECONDS),
    }


DEFAULT_HUI_LUNG_RECIPROCATE_ARGS: dict[str, Any] = build_hui_lung_reciprocate_args()
HUI_LUNG_RECIPROCATE_ARGS: dict[str, Any] = dict(DEFAULT_HUI_LUNG_RECIPROCATE_ARGS)


def _configured_hui_lung_profile() -> dict[str, Any]:
    try:
        from oqlos.hardware.configuration import load_effective_hardware_configuration

        config, _ = load_effective_hardware_configuration()
    except Exception:
        return {}
    hui = config.profiles.get("hui") if isinstance(config.profiles.get("hui"), dict) else {}
    lung = hui.get("lung")
    return dict(lung) if isinstance(lung, dict) else {}


def _int_from_body(body: dict[str, Any], *keys: str, fallback: int) -> int:
    for key in keys:
        if key not in body:
            continue
        try:
            return int(float(body[key]))
        except (TypeError, ValueError):
            continue
    return fallback


def _float_from_body(body: dict[str, Any], *keys: str, fallback: float) -> float:
    for key in keys:
        if key not in body:
            continue
        try:
            return float(body[key])
        except (TypeError, ValueError):
            continue
    return fallback


def _text_from_body(body: dict[str, Any], *keys: str, fallback: str) -> str:
    for key in keys:
        value = str(body.get(key) or "").strip()
        if value:
            return value
    return fallback


def get_hui_lung_valve_id() -> str:
    body = _configured_hui_lung_profile()
    return _text_from_body(body, "valve_id", "valveId", fallback=HUI_AL_LUNG_VALVE_ID)


def get_hui_lung_reciprocate_args() -> dict[str, Any]:
    defaults = dict(DEFAULT_HUI_LUNG_RECIPROCATE_ARGS)
    body = _configured_hui_lung_profile()
    args = body.get("reciprocate_args") or body.get("reciprocateArgs") or body.get("args")
    if isinstance(args, dict):
        body = {**body, **args}

    max_steps_per_second = _int_from_body(
        body,
        "max_steps_per_second",
        "maxStepsPerSecond",
        fallback=HUI_LUNG_MAX_SPEED_STEPS_PER_S,
    )
    speed_steps_per_second = body.get("speed_steps_per_second", body.get("speedStepsPerSecond"))
    if speed_steps_per_second is not None and "speed" not in body:
        speed = steps_per_second_to_raw(speed_steps_per_second, max_steps_per_second=max_steps_per_second)
    else:
        speed = _int_from_body(body, "speed", "target_velocity", "targetVelocity", fallback=int(defaults["speed"]))

    ramp_seconds = _float_from_body(body, "ramp_seconds", "rampSeconds", fallback=float(defaults["ramp_seconds"]))
    acceleration = _int_from_body(
        body,
        "acceleration",
        "acceleration_raw",
        "accelerationRaw",
        fallback=raw_acceleration_for_ramp(speed, ramp_seconds),
    )
    steps = _int_from_body(body, "steps", "stroke_steps", "strokeSteps", fallback=int(defaults["steps"]))

    return {
        **defaults,
        "direction": _text_from_body(body, "direction", fallback=str(defaults["direction"])),
        "start_direction": _text_from_body(
            body,
            "start_direction",
            "startDirection",
            fallback=str(defaults["start_direction"]),
        ),
        "limit_mode": _text_from_body(body, "limit_mode", "limitMode", fallback=str(defaults["limit_mode"])),
        "steps": steps,
        "stroke_steps": _int_from_body(body, "stroke_steps", "strokeSteps", fallback=steps),
        "speed": speed,
        "cycles": _int_from_body(body, "cycles", fallback=int(defaults["cycles"])),
        "pause": _float_from_body(body, "pause", fallback=float(defaults["pause"])),
        "ramp_seconds": ramp_seconds,
        "acceleration": acceleration,
    }
