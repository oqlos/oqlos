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
    idle_state: str = "deenergized"
    deenergize_on_stop: bool = True
    deenergize_on_startup: bool = True
    stop_at_limit: bool = True


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


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


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
    idle_state = str(_pick(src, "idleState", "idle_state") or "deenergized").strip().lower()
    if idle_state not in {"deenergized", "holding"}:
        idle_state = "deenergized"
    idle_default = idle_state == "deenergized"
    stop_mode = str(_pick(src, "stopMode", "stop_mode") or "").strip().lower()
    stop_at_limit_raw = _pick(src, "stopAtLimit", "stop_at_limit")
    if stop_at_limit_raw is not None:
        stop_at_limit_default = _coerce_bool(stop_at_limit_raw, True)
    elif stop_mode == "reach_limit":
        stop_at_limit_default = True
    elif stop_mode in {"immediate", "emergency"}:
        stop_at_limit_default = False
    else:
        stop_at_limit_default = True
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
        idle_state=idle_state,
        deenergize_on_stop=_coerce_bool(
            _pick(src, "deenergizeOnStop", "deenergize_on_stop"), idle_default
        ),
        deenergize_on_startup=_coerce_bool(
            _pick(src, "deenergizeOnStartup", "deenergize_on_startup"), idle_default
        ),
        stop_at_limit=stop_at_limit_default,
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


def _normalize_motor2_direction(direction: str) -> str:
    """Normalize direction aliases to canonical 'left' or 'right'."""
    normalized = direction.strip().lower()
    if normalized in {"reverse", "backward"}:
        return "left"
    if normalized in {"forward"}:
        return "right"
    if normalized not in {"left", "right"}:
        return "left"
    return normalized


def _compute_motor2_cycles(
    cycles: int | None,
    volume_liters: float | None,
    cycle_volume: float,
) -> int:
    """Compute planned cycle count from explicit cycles or volume/cycle-volume ratio."""
    planned = max(1, int(cycles or 1_000_000))
    if volume_liters is not None:
        planned = max(1, int(math.ceil(float(volume_liters) / max(0.001, cycle_volume))))
    return planned


def _compute_motor2_speed(
    steps: int,
    cycles: int,
    speed: int | None,
    duration_seconds: float | None,
    max_speed: int,
    default_speed: int,
) -> tuple[int, int]:
    """Return (requested_speed, effective_speed) given overrides and config."""
    requested = max(1, int(speed or default_speed))
    if duration_seconds is not None:
        duration_speed = motor2_speed_for_duration(steps, cycles, float(duration_seconds))
        requested = min(requested, duration_speed) if speed else duration_speed
    return requested, min(max_speed, requested)


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
    planned_cycles = _compute_motor2_cycles(cycles, volume_liters, planned_cycle_volume)
    requested_speed, effective_speed = _compute_motor2_speed(
        planned_steps, planned_cycles, speed, duration_seconds,
        config.max_steps_per_second, config.default_speed_steps_per_second,
    )
    planned_direction = _normalize_motor2_direction(
        str(direction or config.start_direction or "left")
    )
    return Motor2ReciprocatingPlan(
        direction=planned_direction,
        steps=planned_steps,
        cycles=planned_cycles,
        requested_steps_per_second=requested_speed,
        effective_steps_per_second=effective_speed,
        max_steps_per_second=config.max_steps_per_second,
        acceleration_percent_per_second=(
            acceleration_percent if acceleration_percent is not None
            else config.acceleration_percent_per_second
        ),
        limit_mode=limit_mode or config.limit_mode,
        start_direction=planned_direction,
        volume_liters=volume_liters,
        duration_seconds=duration_seconds,
        cycle_volume_liters=planned_cycle_volume,
    )
