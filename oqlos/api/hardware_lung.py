"""Artificial lung motor and logical lung command routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from oqlos.api.hardware_gateway import get_hardware_gateway
from oqlos.hardware.artificial_lung import execute_command as execute_artificial_lung_command
from oqlos.hardware.artificial_lung import get_peripheral_status as get_artificial_lung_status
from oqlos.hardware.tic249_units import TIC249_DEFAULT_TARGET_VELOCITY

router = APIRouter(tags=["hardware-lung"])


def command_payload(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    command = str(payload.get("command") or "").strip()
    if not command:
        raise HTTPException(status_code=400, detail="command is required")
    args = payload.get("args")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise HTTPException(status_code=400, detail="args must be an object")
    return command, args


async def lung_state_response(action: Any, status: str) -> dict[str, Any]:
    ok = await action()
    return {"ok": ok, "status": status}


@router.post("/lung")
async def set_lung(steps: int = 500, speed: int = TIC249_DEFAULT_TARGET_VELOCITY, cycles: int = 5, pause: float = 0.5):
    """Start artificial lung reciprocating motion (tic249 stepper)."""
    gateway = get_hardware_gateway()
    detailed_result: dict[str, Any] | None = None
    if hasattr(gateway, "set_lung_result"):
        try:
            maybe_result = await gateway.set_lung_result(steps=steps, speed=speed, cycles=cycles, pause=pause)
            if isinstance(maybe_result, dict):
                detailed_result = maybe_result
        except Exception:
            detailed_result = None

    if detailed_result is None:
        ok = await gateway.set_lung(steps=steps, speed=speed, cycles=cycles, pause=pause)
        return {"steps": steps, "speed": speed, "cycles": cycles, "pause": pause, "ok": ok}

    payload: dict[str, Any] = {
        "steps": steps,
        "speed": speed,
        "cycles": cycles,
        "pause": pause,
        "ok": bool(detailed_result.get("success", False)),
    }
    if detailed_result.get("error"):
        payload["error"] = detailed_result.get("error")
    if detailed_result.get("data") is not None:
        payload["data"] = detailed_result.get("data")
    return payload


@router.post("/lung/stop", summary="Emergency stop the artificial lung motor")
async def stop_lung():
    return await lung_state_response(get_hardware_gateway().stop_lung, "stopped")


@router.post("/lung/disable", summary="De-energize the artificial lung motor")
async def disable_lung():
    return await lung_state_response(get_hardware_gateway().disable_lung, "de-energized")


@router.get("/artificial-lung/status")
async def artificial_lung_status():
    """Logical lung state merged with motor connectivity hints."""
    return await get_artificial_lung_status(get_hardware_gateway())


@router.post("/artificial-lung/command")
async def artificial_lung_command(payload: dict[str, Any] = Body(default_factory=dict)):
    """Execute artificial-lung logical commands (set_lpm, lung_*, emergency_stop)."""
    command, args = command_payload(payload)
    return await execute_artificial_lung_command(command, args, get_hardware_gateway())
