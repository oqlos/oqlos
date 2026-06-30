"""Artificial-lung logical state and command dispatch (Tic249-backed)."""

from __future__ import annotations

from typing import Any

from oqlos.hardware.tic249_units import TIC249_DEFAULT_TARGET_VELOCITY

LUNG_STATE: dict[str, Any] = {
    "running": False,
    "lpm": 0,
    "status": "stopped",
}


def _clamp_lpm(value: Any) -> int:
    try:
        lpm = int(value)
    except (TypeError, ValueError):
        lpm = 0
    return max(0, min(50, lpm))


def _command_response(ok: bool, command: str, result: dict[str, Any], *, error: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": ok,
        "peripheral_id": "artificial-lung",
        "command": command,
        "result": result,
        "state": dict(LUNG_STATE),
        "language": "python",
    }
    if error:
        payload["error"] = error
    return payload


async def get_peripheral_status(gateway: Any | None = None) -> dict[str, Any]:
    motor_connected = False
    motor_detail: dict[str, Any] = {}
    if gateway is not None and getattr(gateway, "is_real", False):
        try:
            health = await gateway.health()
            lung_health = health.get("lung") if isinstance(health, dict) else None
            motor_connected = str(lung_health or "").startswith("ok")
            motor_detail["lung_service"] = lung_health
        except Exception as exc:
            motor_detail["lung_service_error"] = str(exc)

    data = {
        **dict(LUNG_STATE),
        "motor_connected": motor_connected,
        **motor_detail,
    }
    return {
        "ok": True,
        "peripheral_id": "artificial-lung",
        "command": "lung_status",
        "result": {"data": data},
    }


async def _lung_cmd_set_lpm(params: dict, gateway: Any) -> dict:
    lpm = _clamp_lpm(params.get("lpm", 0))
    LUNG_STATE["lpm"] = lpm
    LUNG_STATE["status"] = "configured"
    return _command_response(True, "set_lpm", {"message": f"LPM set to {lpm}", "lpm": lpm})


async def _lung_cmd_lung_start(params: dict, gateway: Any) -> dict:
    if LUNG_STATE["lpm"] == 0:
        LUNG_STATE["lpm"] = 10
    LUNG_STATE["running"] = True
    LUNG_STATE["status"] = "running"
    if gateway is not None and getattr(gateway, "is_real", False):
        await gateway.set_lung(
            steps=int(params.get("steps", 500)),
            speed=int(params.get("speed", TIC249_DEFAULT_TARGET_VELOCITY)),
            cycles=int(params.get("cycles", 3)),
            pause=float(params.get("pause", 0.5)),
        )
    return _command_response(
        True,
        "lung_start",
        {"message": "Artificial lung started", "running": True, "lpm": LUNG_STATE["lpm"]},
    )


async def _lung_cmd_lung_stop(params: dict, gateway: Any) -> dict:
    LUNG_STATE["running"] = False
    LUNG_STATE["status"] = "stopped"
    if gateway is not None and getattr(gateway, "is_real", False):
        await gateway.stop_lung()
    return _command_response(True, "lung_stop", {"message": "Artificial lung stopped", "running": False})


async def _lung_cmd_lung_status(params: dict, gateway: Any) -> dict:
    status = await get_peripheral_status(gateway)
    return _command_response(True, "lung_status", status.get("result") or {})


async def _lung_cmd_lung_cycle(params: dict, gateway: Any) -> dict:
    cycles = max(1, int(params.get("cycles", 3)))
    if LUNG_STATE["lpm"] == 0:
        LUNG_STATE["lpm"] = 10
    LUNG_STATE["running"] = True
    LUNG_STATE["status"] = "cycling"
    if gateway is not None and getattr(gateway, "is_real", False):
        await gateway.set_lung(
            steps=int(params.get("steps", 500)),
            speed=int(params.get("speed", TIC249_DEFAULT_TARGET_VELOCITY)),
            cycles=cycles,
            pause=float(params.get("pause", 0.5)),
        )
    return _command_response(
        True,
        "lung_cycle",
        {
            "message": f"Lung cycling {cycles}x at {LUNG_STATE['lpm']} LPM",
            "cycles": cycles,
            "lpm": LUNG_STATE["lpm"],
            "running": True,
        },
    )


async def _lung_cmd_emergency_stop(params: dict, gateway: Any) -> dict:
    LUNG_STATE["running"] = False
    LUNG_STATE["lpm"] = 0
    LUNG_STATE["status"] = "emergency_stopped"
    if gateway is not None and getattr(gateway, "is_real", False):
        await gateway.stop_lung()
    return _command_response(
        True,
        "emergency_stop",
        {
            "message": "EMERGENCY STOP - Lung halted, LPM reset to 0",
            "running": False,
            "lpm": 0,
            "status": "emergency_stopped",
        },
    )


_LUNG_COMMAND_HANDLERS: dict = {
    "set_lpm": _lung_cmd_set_lpm,
    "lung_start": _lung_cmd_lung_start,
    "lung_stop": _lung_cmd_lung_stop,
    "lung_status": _lung_cmd_lung_status,
    "lung_cycle": _lung_cmd_lung_cycle,
    "emergency_stop": _lung_cmd_emergency_stop,
}


async def execute_command(
    command: str, args: dict[str, Any] | None, gateway: Any | None = None
) -> dict[str, Any]:
    cmd = str(command or "").strip().lower()
    handler = _LUNG_COMMAND_HANDLERS.get(cmd)
    if handler is not None:
        return await handler(args or {}, gateway)
    return _command_response(False, cmd, {}, error=f"Unknown artificial-lung command: {cmd}")
