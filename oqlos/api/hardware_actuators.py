"""Direct valve and pump control routes."""

from __future__ import annotations

from fastapi import APIRouter

from oqlos.api.hardware_gateway import get_hardware_gateway

router = APIRouter(tags=["hardware-actuators"])


@router.post("/valve/{valve_id}")
async def set_valve(valve_id: str, value: bool):
    """Directly set a valve (for manual testing)."""
    ok = await get_hardware_gateway().set_valve(valve_id, value)
    return {"valve_id": valve_id, "value": value, "ok": ok}


@router.post("/pump")
async def set_pump(power_pct: float = 0.0):
    """Directly set pump power % (for manual testing)."""
    ok = await get_hardware_gateway().set_pump(power_pct)
    return {"power_pct": power_pct, "ok": ok}
