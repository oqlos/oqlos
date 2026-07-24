"""Modbus wizard and Waveshare diagnose HTTP routes."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException

from oqlos.api.hardware_gateway import snapshot_via_health
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

_settings = get_settings()
router = APIRouter(tags=["hardware-modbus"])
_COIL_TEST_ROLES = {"system", "administrator", "admin"}


def require_coil_test_role(role: str | None) -> str:
    """Reject physical pulse requests outside the privileged TEST personas."""
    normalized = str(role or "").strip().lower()
    if normalized not in _COIL_TEST_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Coil pulse requires the system or administrator role",
        )
    return normalized


@router.get("/modbus/settings")
async def hardware_modbus_settings_get() -> dict[str, Any]:
    """Return baseline/target Modbus baud configuration for the hardware-modbus UI."""
    return read_modbus_baud_settings(_settings)


@router.put("/modbus/settings")
async def hardware_modbus_settings_put(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    """Persist operator-selected target Modbus baud (init still probes 9600 first)."""
    return write_modbus_baud_settings(_settings, payload)


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
    return await asyncio.to_thread(_modbus_wizard_plan)


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
        return {
            "ok": False,
            "error": "module_role must be io, adc, modbus-io or modbus-adc",
        }
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
    new_baudrate: int = Body(default=9600),
    new_parity: str = Body(default="N"),
    confirm_isolated: bool = Body(default=False),
    current_baudrate: int | None = Body(default=None),
) -> dict[str, Any]:
    """Program one isolated module: open at current/baseline baud, write target UART, verify at target."""
    serial = serial_port or str(_settings.modbus_serial_port)
    cur_baud = None if current_baudrate in (None, "") else int(current_baudrate)
    return await asyncio.to_thread(
        _modbus_wizard_program_isolated,
        serial_port=serial,
        current_device_id=int(current_device_id),
        new_device_id=int(new_device_id),
        new_baudrate=int(new_baudrate),
        new_parity=str(new_parity).upper(),
        confirm_isolated=bool(confirm_isolated),
        current_baudrate=cur_baud,
    )
