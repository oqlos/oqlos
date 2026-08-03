"""HUI artificial-lung start/stop actions."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from oqlos.hardware.hui_hold import _set_valve, _success
from oqlos.hardware.hui_readiness import required_plugins_failure
from oqlos.hardware.hui_lung_recipe import (
    HUI_LUNG_STROKE_STEPS,
    get_hui_lung_reciprocate_args,
    get_hui_lung_valve_id,
)
from oqlos.hardware.power_safety import ensure_power_safe

_artificial_lung_running = False

# A lab may explicitly opt into motor-only operation, but production defaults
# must never move Tic249 while the pneumatic valve path is unavailable.
_COMM_FAIL_MARKERS = (
    "timeout",
    "timed out",
    "no response",
    "not available",
    "not connected",
    "io-not-present",
    "not-present",
    "modbus",
    "unreachable",
)


def _env_truthy(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _require_valve() -> bool:
    return _env_truthy("HUI_AL_REQUIRE_VALVE", "1")


def _skip_valve_on_comm_failure() -> bool:
    return _env_truthy("HUI_AL_SKIP_VALVE_ON_COMM_FAILURE", "0")


def _valve_looks_like_comm_failure(valve_op: dict[str, Any]) -> bool:
    """True when set_valve failed because IO bus/plugin is unreachable (not a logic reject)."""
    result = valve_op.get("result")
    # Plugin gateway returns bare False when modbus-io is missing / execute fails hard.
    if result is False or result is None:
        return True
    chunks: list[str] = []
    for key in ("error", "message"):
        if valve_op.get(key) is not None:
            chunks.append(str(valve_op.get(key)))
    if isinstance(result, dict):
        for key in ("error", "message", "detail", "status"):
            if result.get(key) is not None:
                chunks.append(str(result.get(key)))
        if result.get("success") is False and not chunks:
            return True
    blob = " ".join(chunks).lower()
    if not blob:
        return True
    return any(marker in blob for marker in _COMM_FAIL_MARKERS)


async def _run_tic249_reciprocate(gateway: Any) -> dict[str, Any]:
    reciprocate_args = get_hui_lung_reciprocate_args()
    if not getattr(gateway, "is_real", False):
        return {"success": True, "data": {"mock": True, **reciprocate_args}}

    await ensure_power_safe(gateway, operation="hui.motor-tic249.reciprocate")
    if hasattr(gateway, "_get_or_connect_plugin"):
        plugin = await gateway._get_or_connect_plugin("motor-tic249")
        if plugin is None:
            return {"success": False, "error": "motor-tic249 plugin not available"}
        result = await plugin.execute_command("reciprocate", dict(reciprocate_args))
        return result if isinstance(result, dict) else {"success": False, "error": "Invalid Tic249 response"}

    if hasattr(gateway, "set_lung_result"):
        return await gateway.set_lung_result(
            steps=int(reciprocate_args.get("steps", HUI_LUNG_STROKE_STEPS)),
            speed=int(reciprocate_args["speed"]),
            cycles=int(reciprocate_args["cycles"]),
            pause=float(reciprocate_args["pause"]),
        )

    ok = await gateway.set_lung(
        steps=int(reciprocate_args.get("steps", HUI_LUNG_STROKE_STEPS)),
        speed=int(reciprocate_args["speed"]),
        cycles=int(reciprocate_args["cycles"]),
        pause=float(reciprocate_args["pause"]),
    )
    return {"success": bool(ok)}


async def start_hui_artificial_lung(gateway: Any) -> dict[str, Any]:
    global _artificial_lung_running
    readiness_failure = await required_plugins_failure(
        gateway,
        ("modbus-io", "motor-tic249"),
        command="al-start",
        key="al-start",
    )
    if readiness_failure is not None:
        return readiness_failure

    valve_id = get_hui_lung_valve_id()
    valve = await _set_valve(gateway, valve_id, True)
    valve_skipped = False
    if not valve["ok"]:
        if _require_valve() or not (
            _skip_valve_on_comm_failure() and _valve_looks_like_comm_failure(valve)
        ):
            return {"ok": False, "command": "al-start", "error": "Lung valve failed", "operations": [valve]}
        valve_skipped = True
        valve = {
            **valve,
            "skipped": True,
            "warning": (
                f"Valve {valve_id} unavailable (modbus-io); continuing AL with Tic249 only. "
                "Fix RS485 / Waveshare IO for full circuit."
            ),
        }

    lung = await _run_tic249_reciprocate(gateway)
    # Idempotent: already reciprocating is success for AL START.
    if isinstance(lung, dict):
        nested = lung.get("data") if isinstance(lung.get("data"), dict) else {}
        err_txt = str(lung.get("error") or nested.get("error") or "").lower()
        if "already active" in err_txt or "already running" in err_txt:
            lung = {**lung, "success": True, "idempotent_success": True}
    ok = _success(lung)
    if not ok:
        cleanup = None
        if not valve_skipped:
            cleanup = await _set_valve(gateway, valve_id, False)
        return {
            "ok": False,
            "command": "al-start",
            "error": str(lung.get("error") or "Tic249 reciprocate failed") if isinstance(lung, dict) else "Tic249 reciprocate failed",
            "operations": [valve, {"operation": "reciprocate", "ok": False, "result": lung}],
            "cleanup": cleanup,
        }

    _artificial_lung_running = True
    payload: dict[str, Any] = {
        "ok": True,
        "command": "al-start",
        "operations": [valve, {"operation": "reciprocate", "ok": True, "result": lung}],
    }
    if valve_skipped:
        payload["warning"] = valve.get("warning")
        payload["valve_skipped"] = True
    return payload


async def stop_hui_artificial_lung(gateway: Any) -> dict[str, Any]:
    global _artificial_lung_running
    # STOP: Tic stop is critical. Do not block on modbus reconnect — probe once
    # without reconnect, then either close the valve or skip it immediately.
    lung_task = asyncio.create_task(gateway.stop_lung())
    valve_id = get_hui_lung_valve_id()
    readiness = await required_plugins_failure(
        gateway,
        ("modbus-io",),
        command="al-stop",
        key="al-stop",
        check_power=False,
        reconnect=False,
    )
    if readiness is not None:
        valve = {
            "operation": "set_valve",
            "ok": False,
            "valve_id": valve_id,
            "value": False,
            "skipped": True,
            "warning": "Valve close skipped (modbus-io offline); Tic stop applied",
            "result": readiness,
        }
    else:
        valve = await _set_valve(gateway, valve_id, False)

    lung_ok = await lung_task
    _artificial_lung_running = False
    valve_ok = bool(valve.get("ok")) or bool(valve.get("skipped"))
    if not valve_ok and _valve_looks_like_comm_failure(valve):
        valve = {
            **valve,
            "skipped": True,
            "warning": "Valve close skipped (modbus-io offline); Tic stop applied",
        }
        valve_ok = True
    ok = bool(lung_ok) and valve_ok
    payload: dict[str, Any] = {
        "ok": ok,
        "status": "partial" if valve.get("skipped") and lung_ok else ("safe" if ok else "failed"),
        "command": "al-stop",
        "requested": {"motor_stop": True, "valve_close": valve_id},
        "executed": {
            "motor_stop": True,
            "valve_close": not bool(valve.get("skipped")),
        },
        "confirmed": {
            "motor_stopped": bool(lung_ok),
            "valve_closed": bool(valve.get("ok")),
        },
        "operations": [
            {"operation": "stop_lung", "ok": bool(lung_ok), "result": lung_ok},
            valve,
        ],
    }
    if valve.get("skipped"):
        payload["warning"] = valve.get("warning")
        payload["valve_skipped"] = True
    if not ok:
        payload.update({
            "error": "Required hardware unavailable while stopping artificial lung",
            "error_code": "C2004-HW-0012",
            "status_code": 503,
            "safe_to_retry": True,
        })
    return payload
