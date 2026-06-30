"""
Motor2 (TIC-249 stepper motor) action handlers for CQL Interpreter.

Extracted from _interpreter_actions.py to reduce module size.
"""

from __future__ import annotations

import re
from typing import Any, TYPE_CHECKING

import httpx

from oqlos.config import get_settings
from oqlos.core.motor2_runtime import (
    build_motor2_reciprocating_plan,
    motor2_acceleration_raw,
    motor2_max_steps_per_second,
    motor2_speed_for_duration,
    motor2_speed_raw,
    normalize_motor2_runtime_config,
)

if TYPE_CHECKING:
    from oqlos.core.interpreter import CqlInterpreter
    from oqlos.core.base import StepStatus
    from oqlos.core.motor2_runtime import Motor2ReciprocatingPlan


def _normalize_motor2_target(target_lower: str) -> bool:
    normalized = target_lower.replace("_", "-").strip()
    return normalized in {"motor-2", "motor 2", "motor2", "motor-tic249", "tic249"}


def _parse_motor2_direction(value: str) -> str | None:
    normalized = re.sub(r"[\s_-]+", " ", str(value or "").strip().lower())
    if "left" in normalized or "reverse" in normalized:
        return "left"
    if "right" in normalized or "forward" in normalized:
        return "right"
    return None


def _parse_motor2_speed_steps(value: str) -> int | None:
    normalized = str(value or "").strip().lower()
    if "step" not in normalized or "/s" not in normalized:
        return None
    match = re.search(r"([-+]?\d+(?:\.\d+)?)", normalized)
    if not match:
        return None
    return max(1, int(abs(float(match.group(1)))))


def _parse_motor2_float(value: str) -> float | None:
    match = re.search(r"([-+]?\d+(?:[\.,]\d+)?)", str(value or ""))
    if not match:
        return None
    try:
        return abs(float(match.group(1).replace(",", ".")))
    except ValueError:
        return None


def _parse_motor2_duration_seconds(value: str) -> float | None:
    normalized = str(value or "").strip().lower()
    number = _parse_motor2_float(normalized)
    if number is None:
        return None
    if "ms" in normalized:
        return max(0.001, number / 1000.0)
    if "min" in normalized:
        return max(0.001, number * 60.0)
    if "s" in normalized or "sec" in normalized or "sek" in normalized:
        return max(0.001, number)
    return None


def _parse_motor2_volume_liters(value: str) -> float | None:
    normalized = str(value or "").strip().lower()
    if not any(unit in normalized for unit in (" l", "litr", "liter", "litre")):
        return None
    number = _parse_motor2_float(normalized)
    return number if number is not None and number > 0 else None


def _parse_motor2_acceleration(value: str) -> int | None:
    normalized = str(value or "").strip().lower()
    if "acceleration" not in normalized and "accel" not in normalized and "przyspieszenie" not in normalized:
        return None
    match = re.search(r"([-+]?\d+(?:\.\d+)?)", normalized)
    if not match:
        return None
    return max(0, int(abs(float(match.group(1)))))


def _normalize_motor2_value(value: str) -> str:
    return re.sub(r"[\s_-]+", " ", str(value or "").strip().lower())


_MOTOR2_EXACT_MODES: dict = {
    "reciprocating motion": {"action": "mode"},
    "reciprocating": {"action": "mode"},
    "posuwisto zwrotny": {"action": "mode"},
    "ruch posuwisto zwrotny": {"action": "mode"},
    "reverse on limit": {"action": "limit_mode", "limit_mode": "reverse_on_limit"},
    "reverse at limit": {"action": "limit_mode", "limit_mode": "reverse_on_limit"},
    "limit reverse": {"action": "limit_mode", "limit_mode": "reverse_on_limit"},
    "krańcówka zmienia kierunek": {"action": "limit_mode", "limit_mode": "reverse_on_limit"},
    "krancowka zmienia kierunek": {"action": "limit_mode", "limit_mode": "reverse_on_limit"},
}

_MOTOR2_STOP_MODES = {"stop", "halt", "lung stop", "reciprocate stop", "reciprocating stop"}


def _parse_prefixed_motor2_setting(normalized: str) -> "dict[str, Any] | None":
    """Parse prefix-based motor2 settings (stroke, volume, duration, etc.)."""
    if normalized.startswith(("stroke ", "skok ")):
        steps = _parse_motor2_steps(normalized)
        if steps is not None:
            return {"action": "stroke", "steps": steps}
    if normalized.startswith(("cycle volume ", "objetosc cyklu ", "objętość cyklu ")):
        volume = _parse_motor2_volume_liters(normalized)
        if volume is not None:
            return {"action": "cycle_volume", "liters": volume}
    if normalized.startswith(("volume ", "objetosc ", "objętość ")):
        volume = _parse_motor2_volume_liters(normalized)
        if volume is not None:
            return {"action": "volume", "liters": volume}
    if normalized.startswith(("duration ", "time ", "czas ")):
        duration_seconds = _parse_motor2_duration_seconds(normalized)
        if duration_seconds is not None:
            return {"action": "duration", "seconds": duration_seconds}
    if normalized.startswith(("cycles ", "cykle ")):
        cycles = _parse_motor2_steps(normalized)
        if cycles is not None:
            return {"action": "cycles", "cycles": cycles}
    if normalized.startswith(("limit ", "speed limit ")):
        speed = _parse_motor2_speed_steps(normalized)
        if speed is not None:
            return {"action": "limit", "speed": speed}
    return None


def _parse_motor2_reciprocating_setting(value: str) -> "dict[str, Any] | None":
    normalized = _normalize_motor2_value(value)
    exact = _MOTOR2_EXACT_MODES.get(normalized)
    if exact is not None:
        return dict(exact)
    if normalized in _MOTOR2_STOP_MODES:
        return {"action": "stop"}
    prefixed = _parse_prefixed_motor2_setting(normalized)
    if prefixed is not None:
        return prefixed
    if "start" in normalized:
        direction = _parse_motor2_direction(normalized) or "left"
        return {"action": "start", "direction": direction}
    return None


def _parse_motor2_steps(value: str) -> int | None:
    normalized = str(value or "").strip().lower()
    match = re.search(r"([-+]?\d+(?:\.\d+)?)", normalized)
    if not match:
        return None
    return max(1, int(abs(float(match.group(1)))))


def _motor2_speed_raw(steps_per_second: int) -> int:
    return motor2_speed_raw(steps_per_second, _motor2_max_steps_per_second())


def _motor2_max_steps_per_second() -> int:
    return motor2_max_steps_per_second()


def _motor2_effective_steps_per_second(steps_per_second: int) -> int:
    return min(_motor2_max_steps_per_second(), max(1, int(steps_per_second)))


def _motor2_speed_for_duration(steps: int, cycles: int, duration_seconds: float) -> int:
    return motor2_speed_for_duration(steps, cycles, duration_seconds)


def _motor2_acceleration_raw(steps_per_second: int, percent: int | None) -> int | None:
    return motor2_acceleration_raw(steps_per_second, percent, _motor2_max_steps_per_second())


def _post_motor2_move_relative(direction: str, steps: int, speed_raw: int, acceleration_raw: int | None) -> None:
    base_url = get_settings().lung_motor_url.rstrip("/")
    offset = -abs(steps) if direction == "left" else abs(steps)
    payload: dict[str, Any] = {"offset": offset, "speed": speed_raw}
    if acceleration_raw is not None:
        payload["acceleration"] = acceleration_raw
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        response = client.post("/api/move-relative", json=payload)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and data.get("success") is False:
            raise RuntimeError(str(data.get("error") or "motor2 move-relative failed"))


def _post_motor2_reciprocate(
    direction: str,
    steps: int,
    speed_raw: int,
    acceleration_raw: int | None,
    cycles: int,
    pause: float,
    limit_mode: str | None,
) -> None:
    base_url = get_settings().lung_motor_url.rstrip("/")
    start_direction = "reverse" if direction == "left" else "forward"
    payload: dict[str, Any] = {
        "steps": steps,
        "speed": speed_raw,
        "cycles": cycles,
        "pause": pause,
        "direction": start_direction,
        "start_direction": start_direction,
    }
    if acceleration_raw is not None:
        payload["acceleration"] = acceleration_raw
    if limit_mode:
        payload["limit_mode"] = limit_mode
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        response = client.post("/api/reciprocate", json=payload)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and data.get("success") is False:
            raise RuntimeError(str(data.get("error") or "motor2 reciprocate failed"))


def _post_motor2_stop() -> None:
    base_url = get_settings().lung_motor_url.rstrip("/")
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        response = client.post("/api/stop")
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and data.get("success") is False:
            raise RuntimeError(str(data.get("error") or "motor2 stop failed"))


def _motor2_reciprocating_state(interp: "CqlInterpreter") -> dict[str, Any]:
    state = interp.vars.get("__motor2_reciprocating")
    if not isinstance(state, dict):
        state = {}
        interp.vars.set("__motor2_reciprocating", state)
    return state


def _motor2_set_mode(interp: "CqlInterpreter", setting: "dict[str, Any]", state: "dict[str, Any]") -> "StepStatus":
    from oqlos.core.base import StepStatus
    state["enabled"] = True
    interp.out.step("    ⚙️", "SET 'motor 2' 'reciprocating motion'")
    return StepStatus.PASSED


def _motor2_set_limit_mode(interp: "CqlInterpreter", setting: "dict[str, Any]", state: "dict[str, Any]") -> "StepStatus":
    from oqlos.core.base import StepStatus
    state["limit_mode"] = setting.get("limit_mode")
    interp.out.step("    ⚙️", "SET 'motor 2' 'reverse on limit'")
    return StepStatus.PASSED


def _motor2_set_limit(interp: "CqlInterpreter", setting: "dict[str, Any]", state: "dict[str, Any]") -> "StepStatus":
    from oqlos.core.base import StepStatus
    state["speed"] = int(setting["speed"])
    interp.out.step("    ⚙️", f"SET 'motor 2' 'limit {state['speed']} steps/s'")
    return StepStatus.PASSED


def _motor2_set_stroke(interp: "CqlInterpreter", setting: "dict[str, Any]", state: "dict[str, Any]") -> "StepStatus":
    from oqlos.core.base import StepStatus
    state["steps"] = int(setting["steps"])
    interp.out.step("    ⚙️", f"SET 'motor 2' 'stroke {state['steps']} steps'")
    return StepStatus.PASSED


def _motor2_set_cycle_volume(interp: "CqlInterpreter", setting: "dict[str, Any]", state: "dict[str, Any]") -> "StepStatus":
    from oqlos.core.base import StepStatus
    state["cycle_volume_liters"] = float(setting["liters"])
    interp.out.step("    ⚙️", f"SET 'motor 2' 'cycle volume {state['cycle_volume_liters']:g} l'")
    return StepStatus.PASSED


def _motor2_set_volume(interp: "CqlInterpreter", setting: "dict[str, Any]", state: "dict[str, Any]") -> "StepStatus":
    from oqlos.core.base import StepStatus
    state["volume_liters"] = float(setting["liters"])
    interp.out.step("    ⚙️", f"SET 'motor 2' 'volume {state['volume_liters']:g} l'")
    return StepStatus.PASSED


def _motor2_set_duration(interp: "CqlInterpreter", setting: "dict[str, Any]", state: "dict[str, Any]") -> "StepStatus":
    from oqlos.core.base import StepStatus
    state["duration_seconds"] = float(setting["seconds"])
    interp.out.step("    ⚙️", f"SET 'motor 2' 'duration {state['duration_seconds']:g}s'")
    return StepStatus.PASSED


def _motor2_set_cycles(interp: "CqlInterpreter", setting: "dict[str, Any]", state: "dict[str, Any]") -> "StepStatus":
    from oqlos.core.base import StepStatus
    state["cycles"] = int(setting["cycles"])
    interp.out.step("    ⚙️", f"SET 'motor 2' 'cycles {state['cycles']}'")
    return StepStatus.PASSED


def _motor2_do_stop(interp: "CqlInterpreter", setting: "dict[str, Any]", state: "dict[str, Any]") -> "StepStatus":
    from oqlos.core.base import StepStatus
    if interp.mode == "execute":
        try:
            _post_motor2_stop()
        except Exception as exc:
            interp.out.error(f"MOTOR2 STOP failed: {exc}")
            return StepStatus.ERROR
    state["enabled"] = False
    suffix = " ✓" if interp.mode == "execute" else " (simulated)"
    interp.out.step("    →", f"MOTOR2 STOP{suffix}")
    return StepStatus.PASSED


def _motor2_build_plan(
    interp: "CqlInterpreter", setting: "dict[str, Any]", state: "dict[str, Any]"
) -> "Motor2ReciprocatingPlan":
    """Build the reciprocating motion plan from interpreter state and setting."""
    direction = str(setting.get("direction") or interp.vars.get("__motor2_direction") or "right")
    acceleration_percent = interp.vars.get("__motor2_acceleration_percent")
    try:
        acceleration_percent = int(acceleration_percent) if acceleration_percent is not None else None
    except (TypeError, ValueError):
        acceleration_percent = None
    cfg = normalize_motor2_runtime_config()
    return build_motor2_reciprocating_plan(
        cfg,
        direction=direction,
        steps=int(state["steps"]) if state.get("steps") is not None else None,
        speed=int(state["speed"]) if state.get("speed") is not None else None,
        cycles=int(state["cycles"]) if state.get("cycles") is not None else None,
        volume_liters=float(state["volume_liters"]) if state.get("volume_liters") is not None else None,
        duration_seconds=float(state["duration_seconds"]) if state.get("duration_seconds") is not None else None,
        cycle_volume_liters=float(state["cycle_volume_liters"]) if state.get("cycle_volume_liters") is not None else None,
        acceleration_percent=acceleration_percent,
        limit_mode=str(state.get("limit_mode")) if state.get("limit_mode") else None,
    )


def _motor2_step_label(plan: "Motor2ReciprocatingPlan", mode: str) -> str:
    """Format the step output label for a motor2 start action."""
    speed_label = (
        f"{plan.effective_steps_per_second}/s clamped"
        if plan.speed_was_clamped
        else f"{plan.effective_steps_per_second}/s"
    )
    acc_label = (
        f" acc {plan.acceleration_percent_per_second}%/s"
        if plan.acceleration_percent_per_second is not None
        else ""
    )
    suffix = " ✓" if mode == "execute" else " (simulated)"
    return f"MOTOR2 RECIPROCATING {plan.direction.upper()} {plan.steps} @ {speed_label}{acc_label}{suffix}"


def _motor2_do_start(interp: "CqlInterpreter", setting: "dict[str, Any]", state: "dict[str, Any]") -> "StepStatus":
    from oqlos.core.base import StepStatus

    plan = _motor2_build_plan(interp, setting, state)
    pause = float(state.get("pause") or 0.0)
    if interp.mode == "execute":
        try:
            _post_motor2_reciprocate(
                plan.direction,
                plan.steps,
                motor2_speed_raw(plan.effective_steps_per_second, plan.max_steps_per_second),
                motor2_acceleration_raw(
                    plan.effective_steps_per_second,
                    plan.acceleration_percent_per_second,
                    plan.max_steps_per_second,
                ),
                plan.cycles,
                pause,
                plan.limit_mode,
            )
        except Exception as exc:
            interp.out.error(f"MOTOR2 RECIPROCATING {plan.direction.upper()} failed: {exc}")
            return StepStatus.ERROR
    interp.out.step("    →", _motor2_step_label(plan, interp.mode))
    return StepStatus.PASSED


_MOTOR2_RECIPROCATING_HANDLERS: dict = {
    "mode": _motor2_set_mode,
    "limit_mode": _motor2_set_limit_mode,
    "limit": _motor2_set_limit,
    "stroke": _motor2_set_stroke,
    "cycle_volume": _motor2_set_cycle_volume,
    "volume": _motor2_set_volume,
    "duration": _motor2_set_duration,
    "cycles": _motor2_set_cycles,
    "stop": _motor2_do_stop,
    "start": _motor2_do_start,
}


def _handle_motor2_reciprocating_setting(
    interp: "CqlInterpreter",
    setting: "dict[str, Any]",
) -> "StepStatus":
    from oqlos.core.base import StepStatus

    action = setting.get("action")
    state = _motor2_reciprocating_state(interp)
    handler = _MOTOR2_RECIPROCATING_HANDLERS.get(action)
    if handler is not None:
        return handler(interp, setting, state)
    return StepStatus.PASSED


def _try_exec_motor2_set(interp: "CqlInterpreter", target_lower: str, value: str) -> "StepStatus | None":
    if not _normalize_motor2_target(target_lower):
        return None

    from oqlos.core.base import StepStatus

    reciprocating_setting = _parse_motor2_reciprocating_setting(value)
    if reciprocating_setting is not None:
        return _handle_motor2_reciprocating_setting(interp, reciprocating_setting)

    direction = _parse_motor2_direction(value)
    if direction:
        interp.vars.set("__motor2_direction", direction)
        interp.out.step("    ⚙️", f"SET 'motor 2' 'direction {direction}'")
        return StepStatus.PASSED

    acceleration = _parse_motor2_acceleration(value)
    if acceleration is not None:
        interp.vars.set("__motor2_acceleration_percent", acceleration)
        interp.out.step("    ⚙️", f"SET 'motor 2' 'acceleration {acceleration}%/s'")
        return StepStatus.PASSED

    steps_per_second = _parse_motor2_speed_steps(value)
    if steps_per_second is None:
        return None

    direction = str(interp.vars.get("__motor2_direction") or "right")
    acceleration_percent = interp.vars.get("__motor2_acceleration_percent")
    try:
        acceleration_percent = int(acceleration_percent) if acceleration_percent is not None else None
    except (TypeError, ValueError):
        acceleration_percent = None

    if interp.mode == "execute":
        try:
            _post_motor2_move_relative(
                direction,
                steps_per_second,
                _motor2_speed_raw(steps_per_second),
                _motor2_acceleration_raw(steps_per_second, acceleration_percent),
            )
        except Exception as exc:
            interp.out.error(f"MOTOR2 {direction.upper()} failed: {exc}")
            return StepStatus.ERROR

    effective_steps_per_second = _motor2_effective_steps_per_second(steps_per_second)
    speed_label = (
        f"{steps_per_second} @ {effective_steps_per_second}/s clamped"
        if effective_steps_per_second != steps_per_second
        else f"{steps_per_second} @ {steps_per_second}/s"
    )
    suffix = " ✓" if interp.mode == "execute" else " (simulated)"
    interp.out.step("    →", f"MOTOR2 {direction.upper()} {speed_label}{suffix}")
    return StepStatus.PASSED
