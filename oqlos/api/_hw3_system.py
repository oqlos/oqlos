"""Routes: HUI, modbus/diagnosis/wizard, runtime-control, stack-snapshot."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from oqlos.api._hw3_models import _hardware_v1_call, _runtime_control_skipped

sub_router = APIRouter()


@sub_router.get("/hui/actions")
async def hardware_hui_actions_v3() -> dict[str, Any]:
    return await _hardware_v1_call("hui_actions")


@sub_router.post("/hui/shutdown")
async def hardware_hui_shutdown_v3(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    return await _hardware_v1_call("hui_shutdown")


async def _hardware_hui_hold_v3(key: str, action: str) -> dict[str, Any]:
    if action == "start":
        return await _hardware_v1_call("hui_hold_start", key)
    return await _hardware_v1_call("hui_hold_stop", key)


@sub_router.post("/hui/hold/{key}/start")
async def hardware_hui_hold_start_v3(key: str, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    return await _hardware_hui_hold_v3(key, "start")


@sub_router.post("/hui/hold/{key}/stop")
async def hardware_hui_hold_stop_v3(key: str, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    return await _hardware_hui_hold_v3(key, "stop")


@sub_router.post("/hui/al/{command}")
async def hardware_hui_al_command_v3(command: str, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    from oqlos.api import hardware as hw

    normalized = command.strip().lower()
    if normalized == "start":
        return await hw.hui_al_start()
    if normalized == "stop":
        return await hw.hui_al_stop()
    raise HTTPException(status_code=400, detail=f"Unsupported HUI AL command: {command}")


@sub_router.post("/modbus/autoconfigure")
async def hardware_modbus_autoconfigure_v3() -> dict[str, Any]:
    return await _hardware_v1_call("hardware_recover_route", scope="safe")


@sub_router.get("/diagnosis")
async def hardware_diagnosis_v3() -> dict[str, Any]:
    return await _hardware_v1_call("hardware_diagnosis_route", scan="never")


@sub_router.post("/diagnosis/repair")
async def hardware_diagnosis_repair_v3() -> dict[str, Any]:
    return await _hardware_v1_call("hardware_recover_route", scope="safe")


@sub_router.get("/modbus/waveshare-diagnose")
async def hardware_modbus_waveshare_diagnose_v3(exclusive: bool = False) -> dict[str, Any]:
    from oqlos.api import hardware as hw
    return await hw.hardware_modbus_waveshare_diagnose()


@sub_router.get("/modbus/wizard/plan")
async def hardware_modbus_wizard_plan_v3() -> dict[str, Any]:
    return await _hardware_v1_call("hardware_modbus_wizard_plan")


@sub_router.get("/stack/snapshot")
async def hardware_stack_snapshot_v3() -> dict[str, Any]:
    return await _hardware_v1_call("hardware_stack_snapshot")


@sub_router.get("/runtime/status")
async def hardware_runtime_status_v3(serial_port: str = "") -> dict[str, object]:
    return _runtime_control_skipped("status", serial_port=serial_port)


@sub_router.post("/runtime/stop")
async def hardware_runtime_stop_v3(payload: dict[str, object] = Body(default_factory=dict)) -> dict[str, object]:
    return _runtime_control_skipped("stop", serial_port=str(payload.get("serial_port") or ""))


@sub_router.post("/runtime/start")
async def hardware_runtime_start_v3(payload: dict[str, object] = Body(default_factory=dict)) -> dict[str, object]:
    return _runtime_control_skipped("start", mode=str(payload.get("mode") or "light"))


@sub_router.post("/runtime/make")
async def hardware_runtime_make_v3(payload: dict[str, object] = Body(default_factory=dict)) -> dict[str, object]:
    return _runtime_control_skipped("make", target=str(payload.get("target") or ""))


@sub_router.post("/modbus/wizard/probe-isolated")
async def hardware_modbus_wizard_probe_isolated_v3(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    from oqlos.api import hardware as hw
    return await hw.hardware_modbus_wizard_probe_isolated(
        serial_port=str(payload.get("serial_port") or ""),
        baudrates=payload.get("baudrates") if isinstance(payload.get("baudrates"), list) else None,
        parities=payload.get("parities") if isinstance(payload.get("parities"), list) else None,
        device_ids=payload.get("device_ids") if isinstance(payload.get("device_ids"), list) else None,
        module_role=str(payload.get("module_role") or ""),
    )


@sub_router.post("/modbus/wizard/program-isolated")
async def hardware_modbus_wizard_program_isolated_v3(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    from oqlos.api import hardware as hw
    return await hw.hardware_modbus_wizard_program_isolated(
        serial_port=str(payload.get("serial_port") or ""),
        current_device_id=int(payload.get("current_device_id") or 1),
        new_device_id=int(payload.get("new_device_id") or 1),
        new_baudrate=int(payload.get("new_baudrate") or 9600),
        new_parity=str(payload.get("new_parity") or "N"),
        confirm_isolated=bool(payload.get("confirm_isolated")),
    )


@sub_router.post("/runtime-python")
async def hardware_runtime_python_v3(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    return {
        "ok": False,
        "error": "runtime-python execution moved out of c2004 is not enabled in OqlOS",
        "received": payload,
    }
