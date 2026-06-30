"""Shared Pololu Tic T249 unit constants and conversions."""

from __future__ import annotations

from typing import Any

TIC249_TARGET_VELOCITY_SCALE = 10_000
TIC249_DEFAULT_STEPS_PER_SECOND = 1_000
TIC249_DEFAULT_MAX_STEPS_PER_SECOND = 10_000
TIC249_DEFAULT_TARGET_VELOCITY = TIC249_DEFAULT_STEPS_PER_SECOND * TIC249_TARGET_VELOCITY_SCALE
TIC249_DEFAULT_LUNG_PAUSE_SECONDS = 0.5
TIC249_DEFAULT_LUNG_RAMP_SECONDS = 0.5


def steps_per_second_to_raw(
    value: Any,
    *,
    max_steps_per_second: int | float | None = None,
    default_steps_per_second: float | None = None,
) -> int:
    """Convert human steps/s into Tic249 target-velocity raw units."""
    fallback = float(default_steps_per_second or TIC249_DEFAULT_STEPS_PER_SECOND)
    try:
        steps = float(value)
    except (TypeError, ValueError):
        steps = fallback
    cap = max_steps_per_second if max_steps_per_second is not None else TIC249_DEFAULT_MAX_STEPS_PER_SECOND
    try:
        steps = min(steps, float(cap))
    except (TypeError, ValueError):
        pass
    return int(steps * TIC249_TARGET_VELOCITY_SCALE)


def raw_acceleration_for_ramp(raw_speed: int, ramp_seconds: float) -> int:
    """Derive Tic raw acceleration so speed ramps in ``ramp_seconds``."""
    if ramp_seconds <= 0:
        return int(raw_speed)
    return int(raw_speed / ramp_seconds)
