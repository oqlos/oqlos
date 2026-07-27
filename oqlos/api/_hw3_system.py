"""Routes: HUI, modbus/diagnosis/wizard, runtime-control, stack-snapshot."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException

from oqlos.api._hw3_models import _hardware_v1_call, _runtime_control_skipped
from oqlos.errors import OqlosError

sub_router = APIRouter()


def _wizard_integer(
    payload: dict[str, Any],
    field: str,
    default: int | None,
) -> int | None:
    """Parse a wizard integer without leaking ``ValueError`` as HTTP 500."""
    raw_value = payload.get(field)
    if raw_value in (None, ""):
        return default
    if isinstance(raw_value, bool):
        value: int | None = None
    else:
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            value = None
    if value is None:
        raise OqlosError(
            code="api_modbus_wizard_invalid_request",
            status_code=422,
            message=f"{field} must be an integer",
            detail={"field": field, "value": raw_value, "expected": "integer"},
        )
    return value


def _wizard_boolean(payload: dict[str, Any], field: str, default: bool) -> bool:
    """Require a JSON boolean for safety-sensitive wizard confirmations."""
    if field not in payload:
        return default
    raw_value = payload[field]
    if isinstance(raw_value, bool):
        return raw_value
    raise OqlosError(
        code="api_modbus_wizard_invalid_request",
        status_code=422,
        message=f"{field} must be a boolean",
        detail={"field": field, "value": raw_value, "expected": "boolean"},
    )


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


@sub_router.post("/hui/valve/{key}")
async def hardware_hui_valve_v3(key: str, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    return await _hardware_v1_call("hui_valve_key", key)


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
async def hardware_diagnosis_v3(
    scan: str = "never",
    devices: str = "all",
) -> dict[str, Any]:
    return await _hardware_v1_call("hardware_diagnosis_route", scan=scan, devices=devices)


@sub_router.post("/diagnosis/repair")
async def hardware_diagnosis_repair_v3(devices: str = "all") -> dict[str, Any]:
    return await _hardware_v1_call("hardware_recover_route", scope="safe", devices=devices)


@sub_router.get("/modbus/settings")
async def hardware_modbus_settings_v3() -> dict[str, Any]:
    from oqlos.api import hardware_modbus_routes as modbus_hw
    return await modbus_hw.hardware_modbus_settings_get()


@sub_router.put("/modbus/settings")
async def hardware_modbus_settings_update_v3(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    from oqlos.api import hardware_modbus_routes as modbus_hw
    return await modbus_hw.hardware_modbus_settings_put(payload)


@sub_router.get("/modbus/waveshare-diagnose")
async def hardware_modbus_waveshare_diagnose_v3(exclusive: bool = False) -> dict[str, Any]:
    from oqlos.api import hardware_modbus_routes as modbus_hw
    return await modbus_hw.hardware_modbus_waveshare_diagnose()


@sub_router.get("/modbus/profile-channels")
async def hardware_modbus_profile_channels_v3(profile: str = "modbus-adc") -> dict[str, Any]:
    from oqlos.api import hardware_modbus_routes as modbus_hw
    return await modbus_hw.hardware_modbus_profile_channels_get(profile)


@sub_router.put("/modbus/channel-value")
async def hardware_modbus_channel_value_v3(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    from oqlos.api import hardware_modbus_routes as modbus_hw
    return await modbus_hw.hardware_modbus_channel_value_put(payload)


@sub_router.get("/modbus/coil-test/plan")
async def hardware_modbus_coil_test_plan_v3() -> dict[str, Any]:
    from oqlos.api import hardware_modbus_routes as modbus_hw
    return await modbus_hw.hardware_modbus_coil_test_plan_get()


@sub_router.post("/modbus/coil-test/pulse")
async def hardware_modbus_coil_test_pulse_v3(
    payload: dict[str, Any] = Body(default_factory=dict),
    x_connect_role: str | None = Header(default=None, alias="X-Connect-Role"),
) -> dict[str, Any]:
    from oqlos.api import hardware_modbus_routes as modbus_hw
    return await modbus_hw.hardware_modbus_coil_test_pulse_post(payload, x_connect_role)


@sub_router.post("/modbus/coil-test/stop")
async def hardware_modbus_coil_test_stop_v3() -> dict[str, Any]:
    from oqlos.api import hardware_modbus_routes as modbus_hw
    return await modbus_hw.hardware_modbus_coil_test_stop_post()


@sub_router.get("/rtc/status")
async def hardware_rtc_status_v3() -> dict[str, Any]:
    from oqlos.api import hardware_peripherals_routes as periph_hw
    return await periph_hw.rtc_status()


@sub_router.post("/rtc/command")
async def hardware_rtc_command_v3(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    from oqlos.api import hardware_peripherals_routes as periph_hw
    return await periph_hw.rtc_command(payload)


@sub_router.get("/modbus/wizard/plan")
async def hardware_modbus_wizard_plan_v3() -> dict[str, Any]:
    from oqlos.api import hardware_modbus_routes as modbus_hw
    return await modbus_hw.hardware_modbus_wizard_plan()


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


@sub_router.post("/host/reboot")
async def hardware_host_reboot_v3(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    """Reboot the whole hardware board (system-level, via sudo systemctl reboot)."""
    from oqlos.hardware.host_power import schedule_host_reboot

    return schedule_host_reboot(confirm=bool(payload.get("confirm")))


@sub_router.get("/systemd/services")
async def hardware_systemd_services_v3() -> dict[str, Any]:
    """Status of every whitelisted C2004/OqlOS systemd unit on the hardware node."""
    from oqlos.hardware.systemd_services import list_services

    return list_services()


@sub_router.post("/systemd/services/{unit}/{action}")
async def hardware_systemd_control_v3(unit: str, action: str) -> dict[str, Any]:
    """Start/stop/restart/status a whitelisted C2004/OqlOS systemd unit."""
    from oqlos.hardware.systemd_services import control_service, is_whitelisted

    if not is_whitelisted(unit):
        raise HTTPException(status_code=403, detail=f"Unit not in C2004/OqlOS whitelist: {unit}")
    result = control_service(unit, action)
    if not result.get("ok") and result.get("error", "").startswith("Unsupported action"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@sub_router.get("/systemd/services/{unit}/logs")
async def hardware_systemd_logs_v3(unit: str, lines: int = 100) -> dict[str, Any]:
    """Recent journal logs for a whitelisted C2004/OqlOS systemd unit."""
    from oqlos.hardware.systemd_services import is_whitelisted, service_logs

    if not is_whitelisted(unit):
        raise HTTPException(status_code=403, detail=f"Unit not in C2004/OqlOS whitelist: {unit}")
    return service_logs(unit, lines=lines)


@sub_router.get("/logs")
async def hardware_logs_list_v3() -> dict[str, Any]:
    """List log files grouped by day plus whitelisted journal units."""
    from oqlos.hardware.log_files import list_log_files

    return list_log_files()


@sub_router.get("/logs/{log_id:path}")
async def hardware_logs_read_v3(log_id: str, lines: int = 200) -> dict[str, Any]:
    """Tail a whitelisted log file or journal unit."""
    from oqlos.hardware.log_files import read_log

    return read_log(log_id, lines=lines)


@sub_router.get("/startup-diagnostics")
async def hardware_startup_diagnostics_v3() -> dict[str, Any]:
    """Cached result of the diagnostics/auto-repair run performed at OqlOS startup."""
    from oqlos.hardware.startup_diagnostics import last_startup_diagnostics

    result = last_startup_diagnostics()
    if result is None:
        return {"ran": False, "reason": "startup diagnostics have not run yet"}
    return result


@sub_router.post("/modbus/wizard/probe-isolated")
async def hardware_modbus_wizard_probe_isolated_v3(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    from oqlos.api import hardware_modbus_routes as modbus_hw
    return await modbus_hw.hardware_modbus_wizard_probe_isolated(
        serial_port=str(payload.get("serial_port") or ""),
        baudrates=payload.get("baudrates") if isinstance(payload.get("baudrates"), list) else None,
        parities=payload.get("parities") if isinstance(payload.get("parities"), list) else None,
        device_ids=payload.get("device_ids") if isinstance(payload.get("device_ids"), list) else None,
        module_role=str(payload.get("module_role") or ""),
    )


@sub_router.post("/modbus/wizard/program-isolated")
async def hardware_modbus_wizard_program_isolated_v3(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    from oqlos.api import hardware_modbus_routes as modbus_hw
    current_baudrate = _wizard_integer(payload, "current_baudrate", None)
    return await modbus_hw.hardware_modbus_wizard_program_isolated(
        serial_port=str(payload.get("serial_port") or ""),
        current_device_id=_wizard_integer(payload, "current_device_id", 1),
        new_device_id=_wizard_integer(payload, "new_device_id", 1),
        new_baudrate=_wizard_integer(payload, "new_baudrate", 4800),
        new_parity=str(payload.get("new_parity") or "N"),
        confirm_isolated=_wizard_boolean(payload, "confirm_isolated", False),
        current_baudrate=current_baudrate,
    )


@sub_router.post("/runtime-python")
async def hardware_runtime_python_v3(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    raise OqlosError(
        code="api_oql_transport_disabled",
        status_code=503,
        message="runtime-python execution moved out of c2004 is not enabled in OqlOS",
        detail={"received": payload},
    )
