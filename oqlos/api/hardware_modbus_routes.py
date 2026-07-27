"""Modbus wizard and Waveshare diagnose HTTP routes."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException

from oqlos.api.hardware_gateway import snapshot_via_health, try_get_hardware_gateway
from oqlos.api.hardware_modbus_waveshare import _build_waveshare_diagnose_report
from oqlos.api.hardware_modbus_wizard import (
    _modbus_wizard_plan,
    _modbus_wizard_probe_isolated,
    _modbus_wizard_program_isolated,
)
from oqlos.api.hardware_modbus_settings import (
    build_init_baud_sequence,
    effective_modbus_target_baud,
    normalize_probe_baudrates,
    read_modbus_baud_settings,
    write_modbus_baud_settings,
)
from oqlos.config import get_settings
from oqlos.errors import OqlosError

_settings = get_settings()
router = APIRouter(tags=["hardware-modbus"])
_COIL_TEST_ROLES = {"system", "administrator", "admin"}


async def _pause_modbus_plugins_on_serial(serial_port: str) -> tuple[Any | None, set[str]]:
    """Release an RTU adapter while the isolated commissioning wizard owns it."""
    gateway = try_get_hardware_gateway()
    if gateway is None:
        return None, set()
    await gateway.ensure_initialized()

    requested = os.path.realpath(str(serial_port or ""))
    plugin_ids: set[str] = set()
    for plugin_id in ("modbus-io", "modbus-adc"):
        config = gateway._plugin_configs.get(plugin_id)
        if config is None or not config.enabled:
            continue
        configured = os.path.realpath(
            str((config.connection_params or {}).get("serial_port") or "")
        )
        if requested and configured == requested:
            plugin_ids.add(plugin_id)

    if plugin_ids:
        from oqlos.hardware.plugins.registry import PluginRegistry

        for plugin_id in plugin_ids:
            gateway._plugins.pop(plugin_id, None)
            await PluginRegistry.disconnect_plugin(plugin_id)
    return gateway, plugin_ids


def require_coil_test_role(role: str | None) -> str:
    """Reject physical pulse requests outside the privileged TEST personas."""
    normalized = str(role or "").strip().lower()
    if normalized not in _COIL_TEST_ROLES:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Coil pulse requires the system or administrator role",
                "error_code": "C2004-AUTH-0002",
                "c2004_code": "C2004-AUTH-0002",
            },
        )
    return normalized


@router.get("/modbus/settings")
async def hardware_modbus_settings_get() -> dict[str, Any]:
    """Return baseline/target Modbus baud configuration for the hardware-modbus UI."""
    return read_modbus_baud_settings(_settings)


@router.put("/modbus/settings")
async def hardware_modbus_settings_put(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    """Persist and apply Modbus runtime settings (machine baseline is 4800)."""
    result = write_modbus_baud_settings(_settings, payload)
    gateway = try_get_hardware_gateway()
    if gateway is not None and hasattr(gateway, "apply_modbus_user_settings"):
        profile_id = str(payload.get("active_profile") or payload.get("profile_id") or result["active_profile"])
        plugin_ids = (
            {"modbus-io", "modbus-adc"}
            if profile_id == "shared-bus"
            else {profile_id}
        )
        result["runtime_apply"] = await gateway.apply_modbus_user_settings(plugin_ids)
    return result


@router.get("/modbus/waveshare-diagnose")
async def hardware_modbus_waveshare_diagnose() -> dict[str, Any]:
    """Run Waveshare-focused Modbus scan matrix and per-slave register checks."""
    return await snapshot_via_health(_build_waveshare_diagnose_report)


@router.get("/modbus/profile-channels")
async def hardware_modbus_profile_channels_get(profile: str = "modbus-adc") -> dict[str, Any]:
    from oqlos.api.hardware_modbus_channels import read_modbus_profile_channels

    return await read_modbus_profile_channels(profile)


@router.put("/modbus/channel-value")
async def hardware_modbus_channel_value_put(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    from oqlos.api.hardware_modbus_channels import write_modbus_channel_value

    return await write_modbus_channel_value(payload)


@router.get("/modbus/coil-test/plan")
async def hardware_modbus_coil_test_plan_get() -> dict[str, Any]:
    from oqlos.api.hardware_modbus_coil_test import build_coil_test_plan

    return await build_coil_test_plan()


@router.post("/modbus/coil-test/pulse")
async def hardware_modbus_coil_test_pulse_post(
    payload: dict[str, Any] = Body(default_factory=dict),
    x_connect_role: str | None = Header(default=None, alias="X-Connect-Role"),
) -> dict[str, Any]:
    from oqlos.api.hardware_modbus_coil_test import pulse_coil

    require_coil_test_role(x_connect_role)
    return await pulse_coil(payload)


@router.post("/modbus/coil-test/stop")
async def hardware_modbus_coil_test_stop_post() -> dict[str, Any]:
    from oqlos.api.hardware_modbus_coil_test import stop_all_coils

    return await stop_all_coils()


@router.get("/modbus/wizard/plan")
async def hardware_modbus_wizard_plan() -> dict[str, Any]:
    """Return guided step-by-step Modbus configuration plan."""
    # This helper only projects in-memory/env configuration. Sending it through
    # the shared executor lets slow hardware polls starve an otherwise instant
    # UI request when Modbus is unavailable.
    return _modbus_wizard_plan()


@router.post("/modbus/wizard/probe-isolated")
async def hardware_modbus_wizard_probe_isolated(
    serial_port: str = Body(default=""),
    baudrates: list[int] | None = Body(default=None),
    parities: list[str] | None = Body(default=None),
    device_ids: list[int] | None = Body(default=None),
    module_role: str = Body(default=""),
) -> dict[str, Any]:
    """Probe one isolated module before writing address/UART settings."""
    from oqlos.api.hardware_modbus_wizard import normalize_modbus_module_role

    serial = serial_port or str(_settings.modbus_serial_port)
    target = effective_modbus_target_baud(_settings)
    scan_bauds = normalize_probe_baudrates(baudrates, target)
    scan_parities = [str(value).upper() for value in (parities or ["N", "E", "O"])]
    scan_ids = device_ids or [1, 2, 3, 4, 5, 8, 16, 32, 64, 128, 247]
    raw_role = str(module_role or "").strip()
    role = normalize_modbus_module_role(raw_role)
    if raw_role and not role:
        raise OqlosError(
            code="api_modbus_wizard_invalid_request",
            status_code=422,
            message="module_role must be io, adc, modbus-io or modbus-adc",
            detail={
                "field": "module_role",
                "value": raw_role,
                "allowed": ["io", "adc", "modbus-io", "modbus-adc"],
            },
        )
    required_roles = [role] if role else None
    return await asyncio.to_thread(
        _modbus_wizard_probe_isolated,
        serial,
        scan_bauds,
        scan_parities,
        scan_ids,
        required_roles,
    )


@router.post("/modbus/wizard/program-isolated")
async def hardware_modbus_wizard_program_isolated(
    serial_port: str = Body(default=""),
    current_device_id: int = Body(default=1),
    new_device_id: int = Body(default=1),
    new_baudrate: int = Body(default=4800),
    new_parity: str = Body(default="N"),
    confirm_isolated: bool = Body(default=False),
    current_baudrate: int | None = Body(default=None),
) -> dict[str, Any]:
    """Program one isolated module: open at current/baseline baud, write target UART, verify at target."""
    serial = serial_port or str(_settings.modbus_serial_port)
    cur_baud = None if current_baudrate in (None, "") else int(current_baudrate)
    # Reject incomplete safety confirmation before touching the live plugin or
    # acquiring its serial adapter.  The worker repeats this check as defence in
    # depth for non-HTTP callers.
    if not confirm_isolated:
        raise OqlosError(
            code="api_modbus_wizard_invalid_request",
            status_code=422,
            message=(
                "Refusing to write Modbus configuration without "
                "confirm_isolated=true"
            ),
            detail={
                "field": "confirm_isolated",
                "value": False,
                "expected": True,
                "actuation": "configuration-write",
            },
        )
    gateway, paused_plugin_ids = await _pause_modbus_plugins_on_serial(serial)
    try:
        result = await asyncio.to_thread(
            _modbus_wizard_program_isolated,
            serial_port=serial,
            current_device_id=int(current_device_id),
            new_device_id=int(new_device_id),
            new_baudrate=int(new_baudrate),
            new_parity=str(new_parity).upper(),
            confirm_isolated=bool(confirm_isolated),
            current_baudrate=cur_baud,
        )
    except OqlosError as exc:
        if paused_plugin_ids and gateway is not None:
            runtime_apply = await gateway.apply_modbus_user_settings(paused_plugin_ids)
            exc.detail = {**(exc.detail or {}), "runtime_apply": runtime_apply}
        raise
    except Exception as exc:
        result = {
            "ok": False,
            "verified": False,
            "error": f"Modbus isolated programming failed: {exc}",
            "error_type": type(exc).__name__,
        }

    if paused_plugin_ids and gateway is not None:
        result["runtime_apply"] = await gateway.apply_modbus_user_settings(paused_plugin_ids)
    if not bool(result.get("ok")) or not bool(result.get("verified")):
        error_message = str(result.get("error") or "Modbus configuration verification failed")
        normalized_error = error_message.lower()
        if "pimodbus" in normalized_error:
            issue_code = "pimodbus_unavailable"
            status_code = 503
        elif any(
            marker in normalized_error
            for marker in ("port is busy", "resource busy", "could not exclusively lock", "already open")
        ):
            issue_code = "serial_port_busy"
            status_code = 409
        elif result.get("error_type"):
            issue_code = "modbus_preflight_exception"
            status_code = 503
        else:
            issue_code = "hw_modbus_no_response"
            status_code = 503
        raise OqlosError(
            issue_code,
            status_code=status_code,
            message=error_message,
            detail={
                "operation": "modbus.wizard.program_isolated",
                "serial_port": serial,
                "target": result.get("target"),
                "verified": bool(result.get("verified")),
                "runtime_apply": result.get("runtime_apply"),
            },
        )
    return result
