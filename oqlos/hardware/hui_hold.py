"""HUI hold profiles (valve + pump recipes)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from time import perf_counter_ns
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


def _timing_start() -> tuple[str, int]:
    return datetime.now(timezone.utc).isoformat(), perf_counter_ns()


def _timing_fields(started: tuple[str, int] | None = None) -> dict[str, Any]:
    timing = started or _timing_start()
    return {
        "started_at": timing[0],
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": round((perf_counter_ns() - timing[1]) / 1_000_000, 3),
    }


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


def _operation(
    name: str,
    ok: bool,
    *,
    timing: tuple[str, int] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    return {"operation": name, "ok": ok, **_timing_fields(timing), **extra}


def _operation_timeline(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "stage": str(operation.get("operation") or "unknown"),
            "started_at": operation.get("started_at"),
            "completed_at": operation.get("completed_at"),
            "duration_ms": operation.get("duration_ms"),
            "ok": bool(operation.get("ok")),
            **(
                {"cached": bool(operation.get("cached"))}
                if "cached" in operation
                else {}
            ),
        }
        for operation in operations
    ]


def _append_action_timing(
    payload: dict[str, Any],
    *,
    wait_started: tuple[str, int],
    lock_acquired_at: str,
    total_started: tuple[str, int],
) -> dict[str, Any]:
    lock_wait = {
        "stage": "hui.lock_wait",
        "started_at": wait_started[0],
        "completed_at": lock_acquired_at,
        "duration_ms": round((perf_counter_ns() - wait_started[1]) / 1_000_000, 3),
        "ok": True,
    }
    # The lock wait is completed before execution, so calculate its duration at
    # acquisition in callers and replace the provisional value when supplied.
    if "lock_wait_duration_ms" in payload:
        lock_wait["duration_ms"] = payload.pop("lock_wait_duration_ms")
    total = {
        "stage": "hui.total",
        **_timing_fields(total_started),
        "ok": bool(payload.get("ok")),
    }
    timeline = [lock_wait, *list(payload.get("timeline") or []), total]
    payload["timeline"] = timeline
    payload["duration_ms"] = total["duration_ms"]
    return payload


def _shutdown_progress(operations: list[dict[str, Any]]) -> dict[str, Any]:
    pump_operations = [operation for operation in operations if operation.get("operation") == "set_pump"]
    valve_operations = [operation for operation in operations if operation.get("operation") == "set_valve"]
    bulk_operations = [
        operation
        for operation in operations
        if operation.get("operation") == "all_valves_off"
    ]
    bulk_executed = bool(bulk_operations)
    bulk_confirmed = bool(bulk_operations and bulk_operations[-1].get("ok"))
    return {
        "requested": {
            "pump_off": True,
            "valves_off": list(HUI_ALL_VALVE_IDS),
        },
        "executed": {
            "pump_off": bool(pump_operations),
            "valves_off": (
                list(HUI_ALL_VALVE_IDS)
                if bulk_executed
                else [str(operation.get("valve_id")) for operation in valve_operations]
            ),
        },
        "confirmed": {
            "pump_off": bool(pump_operations and pump_operations[-1].get("ok")),
            "valves_off": (
                list(HUI_ALL_VALVE_IDS)
                if bulk_confirmed
                else [
                    str(operation.get("valve_id"))
                    for operation in valve_operations
                    if operation.get("ok")
                ]
            ),
        },
    }


async def _set_valve(gateway: Any, valve_id: str, value: bool) -> dict[str, Any]:
    started = _timing_start()
    result = await gateway.set_valve(valve_id, value)
    return _operation(
        "set_valve",
        _success(result),
        timing=started,
        valve_id=valve_id,
        value=value,
        result=result,
    )


async def _set_pump(gateway: Any, power_pct: float) -> dict[str, Any]:
    started = _timing_start()
    result = await gateway.set_pump(power_pct)
    return _operation(
        "set_pump",
        _success(result),
        timing=started,
        power_pct=power_pct,
        result=result,
    )


async def _set_pump_best_effort(gateway: Any, power_pct: float) -> dict[str, Any]:
    started = _timing_start()
    try:
        result = await gateway.set_pump(power_pct)
        return _operation(
            "set_pump",
            _success(result),
            timing=started,
            power_pct=power_pct,
            result=result,
        )
    except Exception as exc:
        return _operation(
            "set_pump",
            False,
            timing=started,
            power_pct=power_pct,
            error=str(exc),
            best_effort=True,
        )


async def _all_valves_off(gateway: Any) -> dict[str, Any] | None:
    command = getattr(gateway, "all_valves_off", None)
    if not callable(command):
        return None
    started = _timing_start()
    try:
        result = await command()
        return _operation(
            "all_valves_off",
            _success(result),
            timing=started,
            valve_ids=list(HUI_ALL_VALVE_IDS),
            result=result,
        )
    except Exception as exc:
        return _operation(
            "all_valves_off",
            False,
            timing=started,
            valve_ids=list(HUI_ALL_VALVE_IDS),
            error=str(exc),
        )


async def _shutdown_all_hui_hardware_unlocked(
    gateway: Any,
    *,
    modbus_prechecked: bool = False,
) -> dict[str, Any]:
    global _active_hold_key
    _active_hold_key = None
    operations: list[dict[str, Any]] = [await _set_pump_best_effort(gateway, 0.0)]

    # A disconnected Modbus plugin used to trigger the same reconnect probe for
    # every known valve.  With the production RTU timeout this kept the HUI lock
    # occupied for minutes and queued subsequent emergency shutdown requests.
    # Probe once after stopping the independently controlled pump; if the valve
    # controller is unavailable, report that degraded safe-off state immediately.
    readiness_started = _timing_start()
    readiness_failure = None
    if not modbus_prechecked:
        readiness_failure = await required_plugins_failure(
            gateway,
            ("modbus-io",),
            command="shutdown",
            check_power=False,
            reconnect=False,
        )
    readiness_operation = _operation(
        "readiness.modbus-io",
        readiness_failure is None,
        timing=readiness_started,
        cached=modbus_prechecked,
    )
    if readiness_failure is not None:
        readiness_failure.update(
            {
                "status": "partial",
                "degraded": True,
                "operations": operations,
                "timeline": _operation_timeline(
                    [operations[0], readiness_operation, *operations[1:]]
                ),
                **_shutdown_progress(operations),
            }
        )
        return readiness_failure

    bulk_off = await _all_valves_off(gateway)
    if bulk_off is not None:
        operations.append(bulk_off)
    if bulk_off is None or not bulk_off.get("ok"):
        for valve_id in HUI_ALL_VALVE_IDS:
            try:
                operations.append(await _set_valve(gateway, valve_id, False))
            except Exception as exc:
                operations.append(_operation("set_valve", False, valve_id=valve_id, value=False, error=str(exc)))
    progress = _shutdown_progress(operations)
    ok = bool(progress["confirmed"]["pump_off"]) and set(
        progress["confirmed"]["valves_off"]
    ).issuperset(HUI_ALL_VALVE_IDS)
    return {
        "ok": ok,
        "status": "safe" if ok else "partial",
        "degraded": not ok,
        "command": "shutdown",
        "operations": operations,
        "timeline": _operation_timeline(
            [operations[0], readiness_operation, *operations[1:]]
        ),
        **progress,
    }


async def shutdown_all_hui_hardware(gateway: Any) -> dict[str, Any]:
    total_started = _timing_start()
    wait_started = _timing_start()
    async with _HUI_OPERATION_LOCK:
        lock_acquired_at = datetime.now(timezone.utc).isoformat()
        lock_wait_duration_ms = round(
            (perf_counter_ns() - wait_started[1]) / 1_000_000, 3
        )
        payload = await _shutdown_all_hui_hardware_unlocked(gateway)
    payload["lock_wait_duration_ms"] = lock_wait_duration_ms
    return _append_action_timing(
        payload,
        wait_started=wait_started,
        lock_acquired_at=lock_acquired_at,
        total_started=total_started,
    )


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
        "timeline": _operation_timeline(operations),
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
        stagger_started = _timing_start()
        await asyncio.sleep(_VALVE_STAGGER_SECONDS)
        operations.append(
            _operation(
                "valve_stagger",
                True,
                timing=stagger_started,
                seconds=_VALVE_STAGGER_SECONDS,
            )
        )
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
    operations: list[dict[str, Any]] = []
    readiness_started = _timing_start()
    readiness_failure = await required_plugins_failure(
        gateway,
        required_plugins,
        command="hold_start",
        key=hold_key,
    )
    readiness_operation = _operation(
        "readiness.required_plugins",
        readiness_failure is None,
        timing=readiness_started,
        required_hardware=list(required_plugins),
    )
    if readiness_failure is not None:
        readiness_failure["operations"] = []
        readiness_failure["timeline"] = _operation_timeline(
            [readiness_operation]
        )
        return readiness_failure

    shutdown_started = _timing_start()
    shutdown = await _shutdown_all_hui_hardware_unlocked(
        gateway,
        modbus_prechecked=True,
    )
    operations.append(
        _operation(
            "shutdown",
            bool(shutdown.get("ok")),
            timing=shutdown_started,
            result=shutdown,
        )
    )

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
    return {
        "ok": True,
        "command": "hold_start",
        "key": hold_key,
        "operations": operations,
        "timeline": _operation_timeline([readiness_operation, *operations]),
    }


async def start_hui_hold(gateway: Any, key: str) -> dict[str, Any]:
    total_started = _timing_start()
    wait_started = _timing_start()
    async with _HUI_OPERATION_LOCK:
        lock_acquired_at = datetime.now(timezone.utc).isoformat()
        lock_wait_duration_ms = round(
            (perf_counter_ns() - wait_started[1]) / 1_000_000, 3
        )
        payload = await _start_hui_hold_unlocked(gateway, key)
    payload["lock_wait_duration_ms"] = lock_wait_duration_ms
    return _append_action_timing(
        payload,
        wait_started=wait_started,
        lock_acquired_at=lock_acquired_at,
        total_started=total_started,
    )


async def _stop_hui_hold_unlocked(gateway: Any, key: str | None = None) -> dict[str, Any]:
    """Stop a hold and return hardware to a safe state.

    Fail-fast on unavailable required plugins (same contract as start) so a
    silent Modbus slave cannot hang the HTTP request until the C2004 proxy
    maps the stall to C2004-NET-0003 / 504.
    """
    global _active_hold_key
    requested_key = str(key or _active_hold_key or "").strip().lower()

    stopped_key = _active_hold_key
    _active_hold_key = None
    # Always issue the independently controlled pump stop before checking the
    # valve controller. _shutdown... then probes modbus-io once and returns a
    # structured partial result instead of leaving the pump command unsent.
    shutdown = await _shutdown_all_hui_hardware_unlocked(gateway)
    payload = {
        "ok": bool(shutdown.get("ok")),
        "status": shutdown.get("status", "safe" if shutdown.get("ok") else "partial"),
        "command": "hold_stop",
        "key": requested_key or stopped_key,
        "stopped_key": stopped_key,
        "shutdown": shutdown,
        "requested": shutdown.get("requested"),
        "executed": shutdown.get("executed"),
        "confirmed": shutdown.get("confirmed"),
        "timeline": shutdown.get("timeline") or [],
    }
    for field in (
        "error",
        "error_code",
        "status_code",
        "required_hardware",
        "unavailable_hardware",
        "safe_to_retry",
    ):
        if field in shutdown:
            payload[field] = shutdown[field]
    return payload


async def stop_hui_hold(gateway: Any, key: str | None = None) -> dict[str, Any]:
    total_started = _timing_start()
    wait_started = _timing_start()
    async with _HUI_OPERATION_LOCK:
        lock_acquired_at = datetime.now(timezone.utc).isoformat()
        lock_wait_duration_ms = round(
            (perf_counter_ns() - wait_started[1]) / 1_000_000, 3
        )
        payload = await _stop_hui_hold_unlocked(gateway, key)
    payload["lock_wait_duration_ms"] = lock_wait_duration_ms
    return _append_action_timing(
        payload,
        wait_started=wait_started,
        lock_acquired_at=lock_acquired_at,
        total_started=total_started,
    )
