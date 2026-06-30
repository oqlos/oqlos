from __future__ import annotations

from typing import Any

from oqlos.hardware.client.tic249_arg_helpers import tic249_arg
from oqlos.hardware.client.tic249_motion_params import build_reciprocate_params, normalize_motion_params, stroke_steps
from oqlos.hardware.tic249_units import TIC249_DEFAULT_LUNG_PAUSE_SECONDS, TIC249_DEFAULT_STEPS_PER_SECOND


def map_lung_or_reciprocate(command: str, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    default_cycles = 1_000_000 if command == "reciprocating_motion" else 3
    merged = dict(args)
    if command == "reciprocating_motion" and tic249_arg(merged, "speed_unit", "speedUnit") is None:
        merged.setdefault("speed_unit", "steps/s")
    if command == "lung_start":
        if tic249_arg(merged, "speed") is None:
            merged["speed"] = TIC249_DEFAULT_STEPS_PER_SECOND
            merged.setdefault("speed_unit", "steps/s")
        if tic249_arg(merged, "pause") is None and tic249_arg(merged, "tick_seconds", "tickSeconds") is None:
            merged["pause"] = TIC249_DEFAULT_LUNG_PAUSE_SECONDS
    return "reciprocate", build_reciprocate_params(merged, default_cycles=default_cycles)


def map_tic249_command(command: str, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if command in {"tic249_inhale", "tic249_forward"}:
        return "move", normalize_motion_params({"position": stroke_steps(args), **dict(args)})
    if command in {"tic249_exhale", "tic249_backward"}:
        return "move", normalize_motion_params({"position": 0, **dict(args)})
    if command in {"tic249_cycle", "tic249_reciprocate"}:
        return "reciprocate", build_reciprocate_params(args, default_cycles=3)
    if command == "tic249_stop":
        return "stop", {}
    if command in {"deenergize", "disable", "motor_disable", "standby"}:
        return "energize", {"enable": False}
    if command in {"energize", "motor_enable"}:
        return "energize", {"enable": True}
    if command in {"status", "limits", "position"}:
        return "status", {}
    if command in {"stop", "emergency_stop", "lung_stop"}:
        return "stop", {}
    if command in {"home", "home_reverse", "go_home"}:
        return "home", {"direction": "reverse", **dict(args)}
    if command == "home_forward":
        return "home", {"direction": "forward", **dict(args)}
    if command == "move":
        return "move", normalize_motion_params({"position": 0, **dict(args)})
    if command in {"lung_start", "reciprocating_motion"}:
        return map_lung_or_reciprocate(command, args)
    return command, dict(args)
