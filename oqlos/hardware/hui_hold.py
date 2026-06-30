"""HUI hold profiles (valve + pump recipes)."""

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

_VALVE_STAGGER_SECONDS = 0.1
_active_hold_key: str | None = None


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


def _hold_start_failure(
    hold_key: str,
    *,
    error: str,
    operations: list[dict[str, Any]],
    cleanup: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ok": False,
        "command": "hold_start",
        "key": hold_key,
        "error": error,
        "operations": operations,
        "cleanup": cleanup,
    }


async def _engage_hold_valves(
    gateway: Any,
    valve_ids: tuple[str, ...],
    *,
    operations: list[dict[str, Any]],
    hold_key: str,
) -> dict[str, Any] | None:
    for valve_id in valve_ids:
        operation = await _set_valve(gateway, str(valve_id), True)
        operations.append(operation)
        if not operation["ok"]:
            cleanup = await shutdown_all_hui_hardware(gateway)
            return _hold_start_failure(
                hold_key,
                error=f"Valve {valve_id} failed",
                operations=operations,
                cleanup=cleanup,
            )
        await asyncio.sleep(_VALVE_STAGGER_SECONDS)
    return None


async def _engage_hold_pump_if_needed(
    gateway: Any,
    pump_pct: float,
    *,
    operations: list[dict[str, Any]],
    hold_key: str,
) -> dict[str, Any] | None:
    if not pump_pct:
        return None
    operation = await _set_pump(gateway, pump_pct)
    operations.append(operation)
    if operation["ok"]:
        return None
    cleanup = await shutdown_all_hui_hardware(gateway)
    return _hold_start_failure(
        hold_key,
        error="Pump command failed",
        operations=operations,
        cleanup=cleanup,
    )


async def start_hui_hold(gateway: Any, key: str) -> dict[str, Any]:
    global _active_hold_key
    hold_key = str(key or "").strip().lower()
    profile = HUI_HOLD_PROFILES.get(hold_key)
    if profile is None:
        return {"ok": False, "command": "hold_start", "key": hold_key, "error": "Unknown HUI hold key"}

    operations: list[dict[str, Any]] = []
    shutdown = await shutdown_all_hui_hardware(gateway)
    operations.append({"operation": "shutdown", "ok": bool(shutdown.get("ok")), "result": shutdown})

    valve_failure = await _engage_hold_valves(
        gateway,
        tuple(profile["valves_on"]),
        operations=operations,
        hold_key=hold_key,
    )
    if valve_failure is not None:
        return valve_failure

    pump_failure = await _engage_hold_pump_if_needed(
        gateway,
        float(profile["pump_pct"]),
        operations=operations,
        hold_key=hold_key,
    )
    if pump_failure is not None:
        return pump_failure

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
