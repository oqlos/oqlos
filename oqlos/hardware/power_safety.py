"""Shared Raspberry Pi power telemetry and pre-adapter actuation gate."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import threading
from typing import Any

from oqlos.errors import OqlosError
from oqlos.hardware.usb_diagnostics import pi_power_diagnostics

_state_lock = threading.Lock()
_last_signature: tuple[Any, ...] | None = None
_last_event_state: dict[str, Any] | None = None

SAFE_STATE_COMMANDS = frozenset(
    {
        "deenergize",
        "disable",
        "emergency_stop",
        "lung_disable",
        "lung_stop",
        "motor_disable",
        "pump_off",
        "shutdown",
        "standby",
        "stop",
        "stop_lung",
        "valve_off",
    }
)
READ_ONLY_COMMANDS = frozenset(
    {
        "capabilities",
        "diagnose",
        "health",
        "identify",
        "ping",
        "probe",
        "read",
        "read_all",
        "read_config_snapshot",
        "read_io_snapshot",
        "read_sensor",
        "set_lpm",
        "status",
    }
)


@dataclass(frozen=True, slots=True)
class PowerActuationFailure:
    """Typed legacy HUI payload for a power-safety rejection."""

    operation: str
    power: dict[str, Any]
    ok: bool = False
    error: str = "BoardNet supply undervoltage blocks hardware actuation"
    error_code: str = "C2004-HW-0014"
    issue_code: str = "boardnet_undervoltage_active"
    status_code: int = 503
    blocked_before_adapter: bool = True
    safe_to_retry: bool = False

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


def _event_state(power: dict[str, Any]) -> dict[str, Any]:
    return {
        "available": bool(power.get("available")),
        "status": str(power.get("status") or "unknown"),
        "mask": power.get("mask"),
        "mask_hex": power.get("mask_hex"),
        "active": list(power.get("active") or power.get("active_flags") or []),
        "historical": list(
            power.get("historical") or power.get("historical_flags") or []
        ),
        "observed_at": power.get("observed_at"),
        "age_ms": max(0, int(power.get("age_ms") or 0)),
        "source": str(power.get("source") or "vcgencmd.get_throttled"),
    }


def _signature(state: dict[str, Any]) -> tuple[Any, ...]:
    return (
        state["available"],
        state["mask"],
        tuple(state["active"]),
        tuple(state["historical"]),
    )


async def _publish_power_change(
    current: dict[str, Any], previous: dict[str, Any] | None
) -> None:
    from oqlos.api.hardware_events import publish_hardware_event

    await publish_hardware_event(
        "hardware.power_state_changed",
        {"current": current, "previous": previous},
        source="oqlos-power-safety",
        aggregate_id="boardnet-power",
    )


async def observe_power_telemetry(power: dict[str, Any]) -> dict[str, Any]:
    """Normalize a snapshot and emit only an initial/changed throttling state."""
    global _last_event_state, _last_signature
    state = _event_state(power)
    power.update(state)
    signature = _signature(state)
    previous: dict[str, Any] | None = None
    changed = False
    with _state_lock:
        track_state = state["available"] or _last_event_state is not None
        if track_state and signature != _last_signature:
            previous = (
                dict(_last_event_state) if _last_event_state is not None else None
            )
            _last_signature = signature
            _last_event_state = dict(state)
            changed = True
    if changed:
        await _publish_power_change(state, previous)
    return power


async def sample_power_telemetry() -> dict[str, Any]:
    """Read current Pi throttling data without blocking the event loop."""
    power = await asyncio.to_thread(pi_power_diagnostics)
    observed = str(power.get("observed_at") or "")
    try:
        timestamp = datetime.fromisoformat(observed.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        power["age_ms"] = max(
            0, int((datetime.now(timezone.utc) - timestamp).total_seconds() * 1000)
        )
    except (TypeError, ValueError):
        power["age_ms"] = 0
    return await observe_power_telemetry(power)


def has_active_undervoltage(power: dict[str, Any]) -> bool:
    active = power.get("active") or power.get("active_flags") or []
    if "undervoltage" in active:
        return True
    return any(
        item.get("issue_code") == "boardnet_undervoltage_active"
        for item in power.get("errors") or []
        if isinstance(item, dict)
    )


def command_power_policy(command: Any, params: dict[str, Any] | None = None) -> str:
    """Classify a plugin/diagnostic command as read, safe-state or actuation."""
    name = str(command or "").strip().lower().replace("-", "_")
    values = params if isinstance(params, dict) else {}
    if name in SAFE_STATE_COMMANDS:
        return "safe-state"
    if name in READ_ONLY_COMMANDS or name.startswith(("get_", "read_", "list_")):
        return "read-only"
    if name in {"set_coil", "set_valve"} and not bool(values.get("value", False)):
        return "safe-state"
    if name == "energize" and values.get("enable") is False:
        return "safe-state"
    if name in {"set_pump", "set_speed"}:
        try:
            if float(values.get("power_pct", 0.0)) <= 0:
                return "safe-state"
        except (TypeError, ValueError):
            pass
    return "actuation"


async def power_actuation_failure(
    gateway: Any,
    *,
    operation: str,
    safe_state: bool = False,
) -> dict[str, Any] | None:
    """Return the standard failure when active undervoltage blocks actuation."""
    if safe_state or not getattr(gateway, "is_real", False):
        return None
    power = await sample_power_telemetry()
    if not has_active_undervoltage(power):
        return None
    return PowerActuationFailure(operation=operation, power=power).to_payload()


async def ensure_power_safe(
    gateway: Any,
    *,
    operation: str,
    safe_state: bool = False,
) -> None:
    """Raise the shared domain error before unsafe hardware adapter access."""
    failure = await power_actuation_failure(
        gateway, operation=operation, safe_state=safe_state
    )
    if failure is None:
        return
    raise OqlosError(
        code="boardnet_undervoltage_active",
        status_code=503,
        message=str(failure["error"]),
        detail={
            "operation": operation,
            "power": failure["power"],
            "blocked_before_adapter": True,
            "safe_to_retry": False,
        },
    )


def _reset_power_event_state() -> None:
    """Reset process-local change detection (test helper)."""
    global _last_event_state, _last_signature
    with _state_lock:
        _last_signature = None
        _last_event_state = None
