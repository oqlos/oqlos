"""HUI hold profiles (valve + pump recipes)."""

from __future__ import annotations

import asyncio
from typing import Any

from oqlos.hardware.hui_readiness import required_plugins_failure

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
_HUI_OPERATION_LOCK = asyncio.Lock()


def _normalize_hui_profile_key(key: Any) -> str:
    text = str(key or "").strip().lower()
    if text.startswith("hui.hold."):
        return text.removeprefix("hui.hold.")
    return text


def _coerce_valve_ids(value: Any) -> tuple[str, ...] | None:
    if isinstance(value, str):
        items = [item.strip() for item in value.split(",")]
    elif isinstance(value, (list, tuple)):
        items = [str(item).strip() for item in value]
    else:
        return None
    return tuple(item for item in items if item)


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _configured_hui_hold_profiles() -> dict[str, dict[str, Any]]:
    """Profiles from the format-neutral HardwareConfiguration document."""
    try:
        from oqlos.hardware.configuration import load_effective_hardware_configuration

        config, _ = load_effective_hardware_configuration()
    except Exception:
        return {}
    hui = config.profiles.get("hui") if isinstance(config.profiles.get("hui"), dict) else {}
    holds = hui.get("holds") if isinstance(hui.get("holds"), dict) else {}
    profiles: dict[str, dict[str, Any]] = {}
    for key, body in holds.items():
        if not isinstance(body, dict):
            continue
        normalized_key = _normalize_hui_profile_key(key)
        valves = _coerce_valve_ids(body.get("valves_on", body.get("valvesOn")))
        pump_pct = _coerce_float(body.get("pump_pct", body.get("pumpPct")))
        if normalized_key and valves is not None and pump_pct is not None:
            profiles[normalized_key] = {"valves_on": valves, "pump_pct": pump_pct}
    return profiles


def _oql_hui_hold_profiles() -> dict[str, dict[str, Any]]:
    """OQL SET profiles from layers/hardware/hui-profiles.oql (preferred)."""
    try:
        from oqlos.hardware.hui_profiles_oql import load_oql_hui_hold_profiles

        return load_oql_hui_hold_profiles()
    except Exception:
        return {}


def get_hui_hold_profiles() -> dict[str, dict[str, Any]]:
    # One normalized config model plus OQL scenario-layer overrides.
    profiles = {
        key: {"valves_on": tuple(profile["valves_on"]), "pump_pct": float(profile["pump_pct"])}
        for key, profile in HUI_HOLD_PROFILES.items()
    }
    profiles.update(_configured_hui_hold_profiles())
    profiles.update(_oql_hui_hold_profiles())
    return profiles


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


async def _shutdown_all_hui_hardware_unlocked(gateway: Any) -> dict[str, Any]:
    global _active_hold_key
    _active_hold_key = None
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


async def shutdown_all_hui_hardware(gateway: Any) -> dict[str, Any]:
    async with _HUI_OPERATION_LOCK:
        return await _shutdown_all_hui_hardware_unlocked(gateway)


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
            cleanup = await _shutdown_all_hui_hardware_unlocked(gateway)
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
    cleanup = await _shutdown_all_hui_hardware_unlocked(gateway)
    return _hold_start_failure(
        hold_key,
        error="Pump command failed",
        operations=operations,
        cleanup=cleanup,
    )


async def _start_hui_hold_unlocked(gateway: Any, key: str) -> dict[str, Any]:
    global _active_hold_key
    hold_key = str(key or "").strip().lower()
    profile = get_hui_hold_profiles().get(hold_key)
    if profile is None:
        return {"ok": False, "command": "hold_start", "key": hold_key, "error": "Unknown HUI hold key"}

    required_plugins = ["modbus-io"]
    if float(profile["pump_pct"]):
        required_plugins.append("motor-dri0050")
    readiness_failure = await required_plugins_failure(
        gateway,
        required_plugins,
        command="hold_start",
        key=hold_key,
    )
    if readiness_failure is not None:
        return readiness_failure

    operations: list[dict[str, Any]] = []
    shutdown = await _shutdown_all_hui_hardware_unlocked(gateway)
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


async def start_hui_hold(gateway: Any, key: str) -> dict[str, Any]:
    async with _HUI_OPERATION_LOCK:
        return await _start_hui_hold_unlocked(gateway, key)


async def _stop_hui_hold_unlocked(gateway: Any, key: str | None = None) -> dict[str, Any]:
    """Stop a hold and return hardware to a safe state.

    Fail-fast on unavailable required plugins (same contract as start) so a
    silent Modbus slave cannot hang the HTTP request until the C2004 proxy
    maps the stall to C2004-NET-0003 / 504.
    """
    global _active_hold_key
    requested_key = str(key or _active_hold_key or "").strip().lower()

    # Valve shutdown needs modbus-io; pump stop is already best-effort.
    readiness_failure = await required_plugins_failure(
        gateway,
        ["modbus-io"],
        command="hold_stop",
        key=requested_key or None,
        check_power=False,
    )
    if readiness_failure is not None:
        stopped_key = _active_hold_key
        _active_hold_key = None
        readiness_failure["stopped_key"] = stopped_key
        readiness_failure["key"] = requested_key or stopped_key
        return readiness_failure

    stopped_key = _active_hold_key
    shutdown = await _shutdown_all_hui_hardware_unlocked(gateway)
    return {
        "ok": bool(shutdown.get("ok")),
        "command": "hold_stop",
        "key": requested_key or stopped_key,
        "stopped_key": stopped_key,
        "shutdown": shutdown,
    }


async def stop_hui_hold(gateway: Any, key: str | None = None) -> dict[str, Any]:
    async with _HUI_OPERATION_LOCK:
        return await _stop_hui_hold_unlocked(gateway, key)
