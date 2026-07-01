"""Stack snapshot, diagnosis plan, and safe recovery routes."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Query

from oqlos.api.hardware_gateway import get_hardware_gateway
from oqlos.api.hardware_identify import hardware_identify
from oqlos.errors import OqlosError

router = APIRouter(tags=["hardware-diagnosis"])


@router.get("/stack/snapshot")
async def hardware_stack_snapshot() -> dict[str, Any]:
    """Single autodetect + configuration-cycle snapshot (health, ports, wizard plan)."""
    from oqlos.hardware.stack_snapshot import build_hardware_stack_snapshot

    health = await get_hardware_gateway().health()
    return await asyncio.to_thread(build_hardware_stack_snapshot, health)


@router.get("/diagnosis")
async def hardware_diagnosis_route(
    scan: str = Query(default="never", description="Identify scan mode passed before diagnosis"),
) -> dict[str, Any]:
    """Per-device diagnosis plan (environment + recommended actions)."""
    from oqlos.hardware.diagnosis import build_diagnosis_report, report_to_dict

    identify_payload = await hardware_identify(scan=scan)
    report = build_diagnosis_report(identify_payload)
    return report_to_dict(report)


@router.post("/recover")
async def hardware_recover_route(
    scope: str = Query(default="safe", description="Recovery scope: safe = in-process plugin reconnect only"),
) -> dict[str, Any]:
    """Safe auto-recovery inside OqlOS; host sidecar steps are returned as host_actions."""
    from oqlos.hardware.diagnosis import build_diagnosis_report, execute_safe_recover, report_to_dict

    if scope.strip().lower() != "safe":
        raise OqlosError(
            code="api_invalid_recover_scope",
            status_code=400,
            detail={"scope": scope},
        )
    identify_payload = await hardware_identify(scan="never")
    report = build_diagnosis_report(identify_payload)
    execution = await execute_safe_recover(get_hardware_gateway(), report)
    return {
        **execution,
        "device_diagnosis": report_to_dict(report),
        "source": "oqlos.hardware.recover",
    }
