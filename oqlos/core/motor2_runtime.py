"""Domain contract for OQL motor2 / Tic T249 artificial-lung control."""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from typing import Any


@dataclass(frozen=True)
class Motor2RuntimeConfig:
    peripheral_id: str = "motor-tic249"
    stroke_steps: int = 1000
    cycle_volume_liters: float = 5.0
    max_steps_per_second: int = 1000
    default_speed_steps_per_second: int = 1000
    acceleration_percent_per_second: int | None = 100
    speed_unit: str = "steps/s"
    acceleration_unit: str = "%/s"
    limit_mode: str = "reverse_on_limit"
    start_direction: str = "left"


@dataclass(frozen=True)
class Motor2ReciprocatingPlan:
    direction: str
    steps: int
    cycles: int
    requested_steps_per_second: int
    effective_steps_per_second: int
    max_steps_per_second: int
    acceleration_percent_per_second: int | None
    limit_mode: str
    start_direction: str
    volume_liters: float | None = None
    duration_seconds: float | None = None
    cycle_volume_liters: float = 5.0

    @property
    def speed_was_clamped(self) -> bool:
        return self.effective_steps_per_second != self.requested_steps_per_second


def _coerce_int(value: Any, default: int, *, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        parsed = int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        parsed = default
    parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _coerce_float(value: Any, default: float, *, minimum: float = 0.001) -> float:
    try:
        parsed = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, parsed)


def _pick(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in source and source[key] not in (None, ""):
            return source[key]
    return None


def motor2_max_steps_per_second(default: int = 1000) -> int:
    raw = os.getenv("OQLOS_TIC249_MAX_STEPS_PER_SECOND") or os.getenv("TIC249_MAX_STEPS_PER_SECOND")
    return _coerce_int(raw, default, minimum=1)


def normalize_motor2_runtime_config(source: dict[str, Any] | None = None) -> Motor2RuntimeConfig:
    src = source if isinstance(source, dict) else {}
    max_speed = _coerce_int(
        _pick(src, "maxStepsPerSecond", "max_steps_per_second", "maxSpeedStepsPerSecond", "speedLimitStepsPerSecond"),
        motor2_max_steps_per_second(),
    )
    default_speed = _coerce_int(
        _pick(src, "defaultSpeedStepsPerSecond", "default_speed_steps_per_second"),
        min(1000, max_speed),
    )
    acceleration_value = _pick(src, "accelerationPercentPerSecond", "acceleration_percent_per_second", "acceleration")
    acceleration = None if acceleration_value is None else _coerce_int(acceleration_value, 100, minimum=0)
    start_direction = str(_pick(src, "startDirection", "start_direction") or "left").strip().lower()
    if start_direction in {"reverse", "backward"}:
        start_direction = "left"
    if start_direction in {"forward"}:
        start_direction = "right"
    if start_direction not in {"left", "right"}:
        start_direction = "left"
    limit_mode = str(_pick(src, "limitMode", "limit_mode") or "reverse_on_limit").strip().lower()
    if limit_mode in {"reverse on limit", "reverse-at-limit", "reverse at limit"}:
        limit_mode = "reverse_on_limit"
    return Motor2RuntimeConfig(
        peripheral_id=str(_pick(src, "peripheralId", "peripheral_id") or "motor-tic249"),
        stroke_steps=_coerce_int(_pick(src, "strokeSteps", "stroke_steps"), 1000),
        cycle_volume_liters=_coerce_float(_pick(src, "cycleVolumeLiters", "cycle_volume_liters"), 5.0),
        max_steps_per_second=max_speed,
        default_speed_steps_per_second=min(max_speed, default_speed),
        acceleration_percent_per_second=acceleration,
        speed_unit=str(_pick(src, "speedUnit", "speed_unit") or "steps/s"),
        acceleration_unit=str(_pick(src, "accelerationUnit", "acceleration_unit") or "%/s"),
        limit_mode=limit_mode,
        start_direction=start_direction,
    )


def motor2_speed_for_duration(steps: int, cycles: int, duration_seconds: float) -> int:
    half_cycles = max(1, int(cycles) * 2)
    return max(1, int(round((max(1, int(steps)) * half_cycles) / max(0.001, float(duration_seconds)))))


def motor2_acceleration_raw(steps_per_second: int, percent: int | None, max_steps_per_second: int) -> int | None:
    if percent is None:
        return None
    effective = min(max(1, int(max_steps_per_second)), max(1, int(steps_per_second)))
    steps_per_second2 = max(1, int(effective * (percent / 100.0)))
    return min(2_147_483_647, steps_per_second2 * 100)


def motor2_speed_raw(steps_per_second: int, max_steps_per_second: int) -> int:
    effective = min(max(1, int(max_steps_per_second)), max(1, int(steps_per_second)))
    return effective * 10_000


def build_motor2_reciprocating_plan(
    config: Motor2RuntimeConfig,
    *,
    direction: str | None = None,
    steps: int | None = None,
    speed: int | None = None,
    cycles: int | None = None,
    volume_liters: float | None = None,
    duration_seconds: float | None = None,
    cycle_volume_liters: float | None = None,
    acceleration_percent: int | None = None,
    limit_mode: str | None = None,
) -> Motor2ReciprocatingPlan:
    planned_steps = max(1, int(steps or config.stroke_steps))
    planned_cycle_volume = float(cycle_volume_liters or config.cycle_volume_liters)
    planned_cycles = max(1, int(cycles or 1_000_000))
    if volume_liters is not None:
        planned_cycles = max(1, int(math.ceil(float(volume_liters) / max(0.001, planned_cycle_volume))))

    requested_speed = max(1, int(speed or config.default_speed_steps_per_second))
    if duration_seconds is not None:
        duration_speed = motor2_speed_for_duration(planned_steps, planned_cycles, float(duration_seconds))
        requested_speed = min(requested_speed, duration_speed) if speed else duration_speed

    effective_speed = min(config.max_steps_per_second, requested_speed)
    planned_direction = str(direction or config.start_direction or "left").strip().lower()
    if planned_direction in {"reverse", "backward"}:
        planned_direction = "left"
    if planned_direction in {"forward"}:
        planned_direction = "right"
    if planned_direction not in {"left", "right"}:
        planned_direction = "left"

    return Motor2ReciprocatingPlan(
        direction=planned_direction,
        steps=planned_steps,
        cycles=planned_cycles,
        requested_steps_per_second=requested_speed,
        effective_steps_per_second=effective_speed,
        max_steps_per_second=config.max_steps_per_second,
        acceleration_percent_per_second=acceleration_percent
        if acceleration_percent is not None
        else config.acceleration_percent_per_second,
        limit_mode=limit_mode or config.limit_mode,
        start_direction=planned_direction,
        volume_liters=volume_liters,
        duration_seconds=duration_seconds,
        cycle_volume_liters=planned_cycle_volume,
    )
