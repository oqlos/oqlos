"""
Motor2 (TIC-249 stepper motor) action handlers for the OQL interpreter.

Extracted from _interpreter_actions.py to reduce module size.
"""

from __future__ import annotations

import re
import sys
from typing import Any, TYPE_CHECKING

import httpx

from oqlos.core._runtime_settings import lung_motor_url
from oqlos.core.motor2_runtime import (
    build_motor2_reciprocating_plan,
    motor2_acceleration_raw,
    motor2_max_steps_per_second,
    motor2_speed_for_duration,
    motor2_speed_raw,
    normalize_motor2_runtime_config,
)

if TYPE_CHECKING:
    from oqlos.core.interpreter import OqlInterpreter
    from oqlos.core.base import StepStatus
    from oqlos.core.motor2_runtime import Motor2ReciprocatingPlan


def _normalize_motor2_target(target_lower: str) -> bool:
    normalized = target_lower.replace("_", "-").strip()
    return normalized in {
        "motor-2",
        "motor 2",
        "motor2",
        "motor-tic249",
        "tic249",
        "lung-main",
        "lung",
        "pluco",
        "artificial-lung",
    }


def _parse_motor2_direction(value: str) -> str | None:
    normalized = re.sub(r"[\s_-]+", " ", str(value or "").strip().lower())
    if "left" in normalized or "reverse" in normalized or "lewo" in normalized:
        return "left"
    if "right" in normalized or "forward" in normalized or "prawo" in normalized:
        return "right"
    return None


def _parse_motor2_speed_steps(value: str) -> int | None:
    normalized = str(value or "").strip().lower()
    if "step" not in normalized or "/s" not in normalized:
        return None
    return _parse_motor2_positive_int(normalized)


def _parse_motor2_relative_move(value: str) -> dict[str, int] | None:
    """Parse an explicit distance and speed without conflating both values."""
    normalized = re.sub(r"\s+", " ", str(value or "").strip().lower())
    match = re.fullmatch(
        r"(?:move|ruch)\s+(\d+)\s+(?:steps|krok(?:i|ów|ow)?)\s+"
        r"(?:at|z\s+prędkością|z\s+predkoscia)\s+(\d+)\s+"
        r"(?:steps|krok(?:i|ów|ow)?)/s",
        normalized,
    )
    if match:
        return {
            "steps": max(1, int(match.group(1))),
            "speed": max(1, int(match.group(2))),
        }
    # Lung jog shorthand used by hardware-lung-*.oql / connect-scenario.
    bare = re.fullmatch(r"(\d+)\s+(?:steps?|krok(?:i|ów|ow)?)", normalized)
    if not bare:
        return None
    default_speed = normalize_motor2_runtime_config().default_speed_steps_per_second or 80
    return {
        "steps": max(1, int(bare.group(1))),
        "speed": max(1, int(default_speed)),
    }


def _parse_motor2_positive_int(value: str) -> int | None:
    normalized = str(value or "").strip().lower()
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
        # Bare "start" must not force left — honor prior SET direction / __motor2_direction.
        direction = _parse_motor2_direction(normalized)
        setting: dict[str, Any] = {"action": "start"}
        if direction is not None:
            setting["direction"] = direction
        return setting
    return None


def _parse_motor2_steps(value: str) -> int | None:
    return _parse_motor2_positive_int(value)


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
    base_url = lung_motor_url()
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
    base_url = lung_motor_url()
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
    base_url = lung_motor_url()
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        response = client.post("/api/stop")
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and data.get("success") is False:
            raise RuntimeError(str(data.get("error") or "motor2 stop failed"))
        deenergize = client.post("/api/energize", json={"enable": False})
        deenergize.raise_for_status()
        deenergize_data = deenergize.json()
        if isinstance(deenergize_data, dict) and deenergize_data.get("success") is False:
            raise RuntimeError(str(deenergize_data.get("error") or "motor2 deenergize failed"))


def _call_motor2_transport(name: str, fallback: "Any", *args: "Any") -> "Any":
    """Honor legacy monkeypatches on _interpreter_actions while keeping motor2 isolated."""
    compat_module = sys.modules.get("oqlos.core._interpreter_actions")
    transport = getattr(compat_module, name, None) if compat_module is not None else None
    if transport is not None and transport is not fallback:
        return transport(*args)
    return fallback(*args)


def _motor2_reciprocating_state(interp: "OqlInterpreter") -> dict[str, Any]:
    state = interp.vars.get("__motor2_reciprocating")
    if not isinstance(state, dict):
        state = {}
        interp.vars.set("__motor2_reciprocating", state)
    return state


def _motor2_set_state_value(interp: "OqlInterpreter", state: "dict[str, Any]", key: str, value: Any, label: str) -> "StepStatus":
    from oqlos.core.base import StepStatus

    state[key] = value
    interp.out.step("    ⚙️", label)
    return StepStatus.PASSED


def _motor2_state_handler(
    key: str,
    value_fn: "Any",
    label_fn: "Any",
) -> "Any":
    def _handler(interp: "OqlInterpreter", setting: "dict[str, Any]", state: "dict[str, Any]") -> "StepStatus":
        value = value_fn(setting)
        return _motor2_set_state_value(interp, state, key, value, label_fn(value))

    return _handler


def _motor2_do_stop(interp: "OqlInterpreter", setting: "dict[str, Any]", state: "dict[str, Any]") -> "StepStatus":
    from oqlos.core.base import StepStatus
    if interp.mode == "execute":
        try:
            _call_motor2_transport("_post_motor2_stop", _post_motor2_stop)
        except Exception as exc:
            interp.out.error(f"MOTOR2 STOP failed: {exc}")
            return StepStatus.ERROR
    state["enabled"] = False
    suffix = " ✓" if interp.mode == "execute" else " (simulated)"
    interp.out.step("    →", f"MOTOR2 STOP{suffix}")
    return StepStatus.PASSED


def _motor2_build_plan(
    interp: "OqlInterpreter", setting: "dict[str, Any]", state: "dict[str, Any]"
) -> "Motor2ReciprocatingPlan":
    """Build the reciprocating motion plan from interpreter state and setting."""
    direction = str(setting.get("direction") or interp.vars.get("__motor2_direction") or "left")
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


def _motor2_do_start(interp: "OqlInterpreter", setting: "dict[str, Any]", state: "dict[str, Any]") -> "StepStatus":
    from oqlos.core.base import StepStatus

    plan = _motor2_build_plan(interp, setting, state)
    pause = float(state.get("pause") or 0.0)
    if interp.mode == "execute":
        try:
            _call_motor2_transport(
                "_post_motor2_reciprocate",
                _post_motor2_reciprocate,
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
    "mode": _motor2_state_handler(
        "enabled",
        lambda _setting: True,
        lambda _value: "SET 'motor 2' 'reciprocating motion'",
    ),
    "limit_mode": _motor2_state_handler(
        "limit_mode",
        lambda setting: setting.get("limit_mode"),
        lambda _value: "SET 'motor 2' 'reverse on limit'",
    ),
    "limit": _motor2_state_handler(
        "speed",
        lambda setting: int(setting["speed"]),
        lambda value: f"SET 'motor 2' 'limit {value} steps/s'",
    ),
    "stroke": _motor2_state_handler(
        "steps",
        lambda setting: int(setting["steps"]),
        lambda value: f"SET 'motor 2' 'stroke {value} steps'",
    ),
    "cycle_volume": _motor2_state_handler(
        "cycle_volume_liters",
        lambda setting: float(setting["liters"]),
        lambda value: f"SET 'motor 2' 'cycle volume {value:g} l'",
    ),
    "volume": _motor2_state_handler(
        "volume_liters",
        lambda setting: float(setting["liters"]),
        lambda value: f"SET 'motor 2' 'volume {value:g} l'",
    ),
    "duration": _motor2_state_handler(
        "duration_seconds",
        lambda setting: float(setting["seconds"]),
        lambda value: f"SET 'motor 2' 'duration {value:g}s'",
    ),
    "cycles": _motor2_state_handler(
        "cycles",
        lambda setting: int(setting["cycles"]),
        lambda value: f"SET 'motor 2' 'cycles {value}'",
    ),
    "stop": _motor2_do_stop,
    "start": _motor2_do_start,
}


def _handle_motor2_reciprocating_setting(
    interp: "OqlInterpreter",
    setting: "dict[str, Any]",
) -> "StepStatus":
    from oqlos.core.base import StepStatus

    action = setting.get("action")
    state = _motor2_reciprocating_state(interp)
    handler = _MOTOR2_RECIPROCATING_HANDLERS.get(action)
    if handler is not None:
        return handler(interp, setting, state)
    return StepStatus.PASSED


def _try_exec_motor2_set(interp: "OqlInterpreter", target_lower: str, value: str) -> "StepStatus | None":
    if not _normalize_motor2_target(target_lower):
        return None

    from oqlos.core.base import StepStatus
    reciprocating_setting = _parse_motor2_reciprocating_setting(value)
    if reciprocating_setting is not None:
        return _handle_motor2_reciprocating_setting(interp, reciprocating_setting)
    relative_move = _parse_motor2_relative_move(value)
    if relative_move is not None:
        return _exec_motor2_relative_move(interp, relative_move)
    direction = _parse_motor2_direction(value)
    if direction:
        return _exec_motor2_direction(interp, direction)
    acceleration = _parse_motor2_acceleration(value)
    if acceleration is not None:
        return _exec_motor2_acceleration(interp, acceleration)
    steps_per_second = _parse_motor2_speed_steps(value)
    if steps_per_second is None:
        return None
    return _exec_motor2_speed(interp, steps_per_second)


def _exec_motor2_direction(interp: "OqlInterpreter", direction: str):
    from oqlos.core.base import StepStatus
    interp.vars.set("__motor2_direction", direction)
    interp.out.step("    ⚙️", f"SET 'motor 2' 'direction {direction}'")
    return StepStatus.PASSED


def _exec_motor2_acceleration(interp: "OqlInterpreter", acceleration: int):
    from oqlos.core.base import StepStatus
    interp.vars.set("__motor2_acceleration_percent", acceleration)
    interp.out.step("    ⚙️", f"SET 'motor 2' 'acceleration {acceleration}%/s'")
    return StepStatus.PASSED


def _motor2_acceleration_percent(interp: "OqlInterpreter") -> int | None:
    value = interp.vars.get("__motor2_acceleration_percent")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _exec_motor2_relative_move(interp: "OqlInterpreter", relative_move: dict):
    from oqlos.core.base import StepStatus
    direction = str(interp.vars.get("__motor2_direction") or "right")
    acceleration_percent = _motor2_acceleration_percent(interp)
    requested_speed = int(relative_move["speed"])
    effective_speed = _motor2_effective_steps_per_second(requested_speed)
    if not _send_motor2_move(
        interp, direction, int(relative_move["steps"]), effective_speed, acceleration_percent
    ):
        return StepStatus.ERROR
    speed_label = f"{requested_speed}/s → {effective_speed}/s clamped" if requested_speed != effective_speed else f"{effective_speed}/s"
    suffix = " ✓" if interp.mode == "execute" else " (simulated)"
    interp.out.step(
        "    →",
        f"MOTOR2 {direction.upper()} {relative_move['steps']} steps @ {speed_label}{suffix}",
    )
    return StepStatus.PASSED


def _send_motor2_move(
    interp: "OqlInterpreter", direction: str, steps: int,
    speed: int, acceleration_percent: int | None,
) -> bool:
    if interp.mode != "execute":
        return True
    try:
        _call_motor2_transport(
            "_post_motor2_move_relative", _post_motor2_move_relative, direction,
            steps, _motor2_speed_raw(speed), _motor2_acceleration_raw(speed, acceleration_percent),
        )
    except Exception as exc:
        interp.out.error(f"MOTOR2 {direction.upper()} failed: {exc}")
        return False
    return True


def _exec_motor2_speed(interp: "OqlInterpreter", steps_per_second: int):
    from oqlos.core.base import StepStatus
    direction = str(interp.vars.get("__motor2_direction") or "right")
    acceleration_percent = _motor2_acceleration_percent(interp)
    if not _send_motor2_move(interp, direction, steps_per_second, steps_per_second, acceleration_percent):
        return StepStatus.ERROR
    effective = _motor2_effective_steps_per_second(steps_per_second)
    speed_label = (
        f"{steps_per_second} @ {effective}/s clamped"
        if effective != steps_per_second else f"{steps_per_second} @ {steps_per_second}/s"
    )
    suffix = " ✓" if interp.mode == "execute" else " (simulated)"
    interp.out.step("    →", f"MOTOR2 {direction.upper()} {speed_label}{suffix}")
    return StepStatus.PASSED
