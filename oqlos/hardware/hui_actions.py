"""HUI domain actions for OqlOS-owned hardware recipes."""

from __future__ import annotations

import asyncio
from typing import Any


HUI_HOLD_PROFILES: dict[str, dict[str, Any]] = {
    "head-inflate": {"valves_on": ("valve-5", "valve-2"), "pump_pct": 70.0},
    "head-deflate": {"valves_on": ("valve-3", "valve-6"), "pump_pct": 0.0},
    "lp-pwm-plus5": {"valves_on": ("valve-5",), "pump_pct": 50.0},
    "lp-pwm-plus10": {"valves_on": ("valve-5",), "pump_pct": 100.0},
    "lp-pwm-minus5": {"valves_on": ("valve-6",), "pump_pct": 50.0},
    "lp-pwm-minus10": {"valves_on": ("valve-6",), "pump_pct": 100.0},
    "lp-bleed": {"valves_on": ("valve-4",), "pump_pct": 0.0},
}

HUI_ALL_VALVE_IDS = (
    "valve-1",
    "valve-2",
    "valve-3",
    "valve-4",
    "valve-5",
    "valve-6",
    "valve-7",
    "valve-8",
    "valve-nc",
    "valve-sc",
    "valve-wc",
)

HUI_AL_LUNG_VALVE_ID = "valve-4"
HUI_LUNG_STROKE_STEPS = 1_000_000
HUI_LUNG_MAX_SPEED_STEPS_PER_S = 1000
HUI_LUNG_PAUSE_SECONDS = 0.5
HUI_LUNG_RAMP_SECONDS = 0.5
_TIC249_RAW_SPEED_FACTOR = 10_000
_TIC249_LUNG_SPEED_RAW = HUI_LUNG_MAX_SPEED_STEPS_PER_S * _TIC249_RAW_SPEED_FACTOR
_TIC249_LUNG_ACCELERATION_RAW = int(_TIC249_LUNG_SPEED_RAW / HUI_LUNG_RAMP_SECONDS)

HUI_LUNG_RECIPROCATE_ARGS: dict[str, Any] = {
    "direction": "right",
    "start_direction": "right",
    "limit_mode": "reverse_on_limit",
    "steps": HUI_LUNG_STROKE_STEPS,
    "stroke_steps": HUI_LUNG_STROKE_STEPS,
    "speed": _TIC249_LUNG_SPEED_RAW,
    "cycles": 1_000_000,
    "pause": HUI_LUNG_PAUSE_SECONDS,
    "ramp_seconds": HUI_LUNG_RAMP_SECONDS,
    "acceleration": _TIC249_LUNG_ACCELERATION_RAW,
}

_VALVE_STAGGER_SECONDS = 0.1
_active_hold_key: str | None = None
_artificial_lung_running = False


def _success(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        if "success" in value:
            return bool(value.get("success"))
        if "ok" in value:
            return bool(value.get("ok"))
    return bool(value)


def _operation(name: str, ok: bool, **extra: Any) -> dict[str, Any]:
    return {"operation": name, "ok": ok, **extra}


async def _set_valve(gateway: Any, valve_id: str, value: bool) -> dict[str, Any]:
    result = await gateway.set_valve(valve_id, value)
    return _operation("set_valve", _success(result), valve_id=valve_id, value=value, result=result)


async def _set_pump(gateway: Any, power_pct: float) -> dict[str, Any]:
    result = await gateway.set_pump(power_pct)
    return _operation("set_pump", _success(result), power_pct=power_pct, result=result)


async def _set_pump_best_effort(gateway: Any, power_pct: float) -> dict[str, Any]:
    try:
        return await _set_pump(gateway, power_pct)
    except Exception as exc:
        return _operation("set_pump", False, power_pct=power_pct, error=str(exc), best_effort=True)


async def shutdown_all_hui_hardware(gateway: Any) -> dict[str, Any]:
    operations: list[dict[str, Any]] = [await _set_pump_best_effort(gateway, 0.0)]
    for valve_id in HUI_ALL_VALVE_IDS:
        try:
            operations.append(await _set_valve(gateway, valve_id, False))
        except Exception as exc:
            operations.append(_operation("set_valve", False, valve_id=valve_id, value=False, error=str(exc)))
    return {
        "ok": all(operation.get("ok") for operation in operations),
        "command": "shutdown",
        "operations": operations,
    }


def list_hui_actions() -> dict[str, Any]:
    return {
        "ok": True,
        "hold_keys": list(HUI_HOLD_PROFILES.keys()),
        "al_keys": ["al-start", "al-stop"],
        "profiles": {
            key: {
                "valves_on": list(profile["valves_on"]),
                "pump_pct": profile["pump_pct"],
            }
            for key, profile in HUI_HOLD_PROFILES.items()
        },
        "artificial_lung": {
            "valve_id": HUI_AL_LUNG_VALVE_ID,
            "reciprocate_args": dict(HUI_LUNG_RECIPROCATE_ARGS),
        },
    }


async def start_hui_hold(gateway: Any, key: str) -> dict[str, Any]:
    global _active_hold_key
    hold_key = str(key or "").strip().lower()
    profile = HUI_HOLD_PROFILES.get(hold_key)
    if profile is None:
        return {"ok": False, "command": "hold_start", "key": hold_key, "error": "Unknown HUI hold key"}

    operations: list[dict[str, Any]] = []
    shutdown = await shutdown_all_hui_hardware(gateway)
    operations.append({"operation": "shutdown", "ok": bool(shutdown.get("ok")), "result": shutdown})

    for valve_id in profile["valves_on"]:
        operation = await _set_valve(gateway, str(valve_id), True)
        operations.append(operation)
        if not operation["ok"]:
            cleanup = await shutdown_all_hui_hardware(gateway)
            return {
                "ok": False,
                "command": "hold_start",
                "key": hold_key,
                "error": f"Valve {valve_id} failed",
                "operations": operations,
                "cleanup": cleanup,
            }
        await asyncio.sleep(_VALVE_STAGGER_SECONDS)

    pump_pct = float(profile["pump_pct"])
    if pump_pct:
        operation = await _set_pump(gateway, pump_pct)
        operations.append(operation)
        if not operation["ok"]:
            cleanup = await shutdown_all_hui_hardware(gateway)
            return {
                "ok": False,
                "command": "hold_start",
                "key": hold_key,
                "error": "Pump command failed",
                "operations": operations,
                "cleanup": cleanup,
            }

    _active_hold_key = hold_key
    return {"ok": True, "command": "hold_start", "key": hold_key, "operations": operations}


async def stop_hui_hold(gateway: Any, key: str | None = None) -> dict[str, Any]:
    global _active_hold_key
    requested_key = str(key or _active_hold_key or "").strip().lower()
    shutdown = await shutdown_all_hui_hardware(gateway)
    stopped_key = _active_hold_key
    _active_hold_key = None
    return {
        "ok": bool(shutdown.get("ok")),
        "command": "hold_stop",
        "key": requested_key or stopped_key,
        "stopped_key": stopped_key,
        "shutdown": shutdown,
    }


async def _run_tic249_reciprocate(gateway: Any) -> dict[str, Any]:
    if not getattr(gateway, "is_real", False):
        return {"success": True, "data": {"mock": True, **HUI_LUNG_RECIPROCATE_ARGS}}

    if hasattr(gateway, "_get_or_connect_plugin"):
        plugin = await gateway._get_or_connect_plugin("motor-tic249")
        if plugin is None:
            return {"success": False, "error": "motor-tic249 plugin not available"}
        result = await plugin.execute_command("reciprocate", dict(HUI_LUNG_RECIPROCATE_ARGS))
        return result if isinstance(result, dict) else {"success": False, "error": "Invalid Tic249 response"}

    if hasattr(gateway, "set_lung_result"):
        return await gateway.set_lung_result(
            steps=HUI_LUNG_STROKE_STEPS,
            speed=HUI_LUNG_RECIPROCATE_ARGS["speed"],
            cycles=HUI_LUNG_RECIPROCATE_ARGS["cycles"],
            pause=HUI_LUNG_RECIPROCATE_ARGS["pause"],
        )

    ok = await gateway.set_lung(
        steps=HUI_LUNG_STROKE_STEPS,
        speed=HUI_LUNG_RECIPROCATE_ARGS["speed"],
        cycles=HUI_LUNG_RECIPROCATE_ARGS["cycles"],
        pause=HUI_LUNG_RECIPROCATE_ARGS["pause"],
    )
    return {"success": bool(ok)}


async def start_hui_artificial_lung(gateway: Any) -> dict[str, Any]:
    global _artificial_lung_running
    valve = await _set_valve(gateway, HUI_AL_LUNG_VALVE_ID, True)
    if not valve["ok"]:
        return {"ok": False, "command": "al-start", "error": "Lung valve failed", "operations": [valve]}

    lung = await _run_tic249_reciprocate(gateway)
    ok = _success(lung)
    if not ok:
        cleanup = await _set_valve(gateway, HUI_AL_LUNG_VALVE_ID, False)
        return {
            "ok": False,
            "command": "al-start",
            "error": str(lung.get("error") or "Tic249 reciprocate failed") if isinstance(lung, dict) else "Tic249 reciprocate failed",
            "operations": [valve, {"operation": "reciprocate", "ok": False, "result": lung}],
            "cleanup": cleanup,
        }

    _artificial_lung_running = True
    return {
        "ok": True,
        "command": "al-start",
        "operations": [valve, {"operation": "reciprocate", "ok": True, "result": lung}],
    }


async def stop_hui_artificial_lung(gateway: Any) -> dict[str, Any]:
    global _artificial_lung_running
    lung_ok = await gateway.stop_lung()
    valve = await _set_valve(gateway, HUI_AL_LUNG_VALVE_ID, False)
    _artificial_lung_running = False
    return {
        "ok": bool(lung_ok) and bool(valve["ok"]),
        "command": "al-stop",
        "operations": [
            {"operation": "stop_lung", "ok": bool(lung_ok), "result": lung_ok},
            valve,
        ],
    }
