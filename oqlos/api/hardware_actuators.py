"""Direct valve and pump control routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from oqlos.api.hardware_gateway import get_hardware_gateway
from oqlos.errors import OqlosError

router = APIRouter(tags=["hardware-actuators"])


def _pump_success(result: Any) -> bool:
    if isinstance(result, dict):
        return bool(result.get("success"))
    return bool(result)


@router.post("/valve/{valve_id}")
async def set_valve(valve_id: str, value: bool):
    """Directly set a valve (for manual testing)."""
    ok = await get_hardware_gateway().set_valve(valve_id, value)
    return {"valve_id": valve_id, "value": value, "ok": ok}


@router.post("/pump")
async def set_pump(power_pct: float = 0.0):
    """Directly set pump power % (for manual testing)."""
    result = await get_hardware_gateway().set_pump(power_pct)
    if not _pump_success(result):
        error = (
            str(result.get("error") or "Motor plugin not available")
            if isinstance(result, dict)
            else "Motor plugin not available"
        )
        raise OqlosError(
            code="hw_dri0050_sidecar_unreachable",
            status_code=503,
            message=error,
            detail={"power_pct": power_pct, "result": result},
        )
    payload: dict[str, Any] = {"power_pct": power_pct, "ok": True}
    if isinstance(result, dict) and result.get("data") is not None:
        payload["data"] = result.get("data")
    return payload
