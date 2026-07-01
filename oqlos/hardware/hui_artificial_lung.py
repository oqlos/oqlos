"""HUI artificial-lung start/stop actions."""

from __future__ import annotations

from typing import Any

from oqlos.hardware.hui_hold import _set_valve, _success
from oqlos.hardware.hui_lung_recipe import (
    HUI_LUNG_STROKE_STEPS,
    get_hui_lung_reciprocate_args,
    get_hui_lung_valve_id,
)

_artificial_lung_running = False


async def _run_tic249_reciprocate(gateway: Any) -> dict[str, Any]:
    reciprocate_args = get_hui_lung_reciprocate_args()
    if not getattr(gateway, "is_real", False):
        return {"success": True, "data": {"mock": True, **reciprocate_args}}

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
    valve_id = get_hui_lung_valve_id()
    valve = await _set_valve(gateway, valve_id, True)
    if not valve["ok"]:
        return {"ok": False, "command": "al-start", "error": "Lung valve failed", "operations": [valve]}

    lung = await _run_tic249_reciprocate(gateway)
    ok = _success(lung)
    if not ok:
        cleanup = await _set_valve(gateway, valve_id, False)
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
    valve = await _set_valve(gateway, get_hui_lung_valve_id(), False)
    _artificial_lung_running = False
    return {
        "ok": bool(lung_ok) and bool(valve["ok"]),
        "command": "al-stop",
        "operations": [
            {"operation": "stop_lung", "ok": bool(lung_ok), "result": lung_ok},
            valve,
        ],
    }
