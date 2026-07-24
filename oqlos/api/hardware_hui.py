"""HUI hold / artificial-lung routes for the hardware API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from oqlos.api.hardware_gateway import get_hardware_gateway
from oqlos.hardware.hui_actions import (
    list_hui_actions,
    run_hui_valve_key,
    shutdown_all_hui_hardware,
    start_hui_artificial_lung,
    start_hui_hold,
    stop_hui_artificial_lung,
    stop_hui_hold,
)

router = APIRouter(tags=["hardware-hui"])


def raise_if_hui_failed(payload: dict[str, Any]) -> None:
    if not payload.get("ok"):
        raise HTTPException(status_code=int(payload.get("status_code") or 400), detail=payload)


async def start_hui_action(action: Any, *args: Any) -> dict[str, Any]:
    payload = await action(get_hardware_gateway(), *args)
    raise_if_hui_failed(payload)
    return payload


@router.get("/hui/actions")
async def hui_actions() -> dict[str, Any]:
    """Return OqlOS-owned HUI action recipes."""
    return list_hui_actions()


@router.post("/hui/shutdown", summary="Stop HUI pump/valve actions using the canonical OqlOS recipe")
async def hui_shutdown() -> dict[str, Any]:
    return await shutdown_all_hui_hardware(get_hardware_gateway())


@router.post("/hui/hold/{key}/start", summary="Start a named HUI hold action")
async def hui_hold_start(key: str) -> dict[str, Any]:
    return await start_hui_action(start_hui_hold, key)


@router.post("/hui/hold/{key}/stop", summary="Stop a named HUI hold action and return hardware to a safe state")
async def hui_hold_stop(key: str) -> dict[str, Any]:
    # Same fail-fast HTTP mapping as start (503 + C2004-HW-0012 when plugins down).
    return await start_hui_action(stop_hui_hold, key)


@router.post("/hui/valve/{key}", summary="Run a named HUI valve toggle (WC press/bleed)")
async def hui_valve_key(key: str) -> dict[str, Any]:
    return await start_hui_action(run_hui_valve_key, key)


@router.post("/hui/al/start", summary="Start the HUI artificial-lung action")
async def hui_al_start() -> dict[str, Any]:
    return await start_hui_action(start_hui_artificial_lung)


@router.post("/hui/al/stop", summary="Stop the HUI artificial-lung action")
async def hui_al_stop() -> dict[str, Any]:
    return await stop_hui_artificial_lung(get_hardware_gateway())
