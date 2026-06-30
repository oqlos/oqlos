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


HUI_LUNG_RECIPROCATE_ARGS: dict[str, Any] = build_hui_lung_reciprocate_args()
