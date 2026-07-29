"""Stack snapshot, diagnosis plan, and safe recovery routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from oqlos.api.hardware_gateway import get_hardware_gateway, snapshot_via_health
from oqlos.api.hardware_identify import hardware_identify
from oqlos.errors import OqlosError

router = APIRouter(tags=["hardware-diagnosis"])


@router.get("/stack/snapshot")
async def hardware_stack_snapshot() -> dict[str, Any]:
    """Single autodetect + configuration-cycle snapshot (health, ports, wizard plan)."""
    from oqlos.hardware.stack_snapshot import build_hardware_stack_snapshot

    return await snapshot_via_health(build_hardware_stack_snapshot)


@router.get("/diagnosis")
async def hardware_diagnosis_route(
    scan: str = Query(default="never", description="Identify scan mode passed before diagnosis"),
    devices: str = Query(default="all", description="Device subset: all | motors"),
) -> dict[str, Any]:
    """Per-device diagnosis plan (environment + recommended actions)."""
    from oqlos.hardware.diagnosis import build_diagnosis_report, filter_diagnosis_dict_for_devices, report_to_dict

    identify_payload = await hardware_identify(scan=scan)
    report = build_diagnosis_report(identify_payload)
    payload = report_to_dict(report)
    return filter_diagnosis_dict_for_devices(payload, devices)


@router.post("/recover")
async def hardware_recover_route(
    scope: str = Query(default="safe", description="Recovery scope: safe = in-process plugin reconnect only"),
    devices: str = Query(default="all", description="Device subset: all | motors"),
) -> dict[str, Any]:
    """Safe auto-recovery inside OqlOS; host sidecar steps are returned as host_actions."""
    from oqlos.hardware.diagnosis import (
        build_diagnosis_report,
        execute_safe_recover,
        filter_diagnosis_dict_for_devices,
        report_to_dict,
        resolve_recover_plugin_ids,
    )

    if scope.strip().lower() != "safe":
        raise OqlosError(
            code="api_invalid_recover_scope",
            status_code=422,
            detail={"scope": scope},
        )
    identify_payload = await hardware_identify(scan="never")
    report = build_diagnosis_report(identify_payload)
    plugin_ids = resolve_recover_plugin_ids(devices)
    execution = await execute_safe_recover(get_hardware_gateway(), report, plugin_ids=plugin_ids)
    device_diagnosis = filter_diagnosis_dict_for_devices(report_to_dict(report), devices)
    return {
        **execution,
        "device_diagnosis": device_diagnosis,
        "source": "oqlos.hardware.recover",
    }
