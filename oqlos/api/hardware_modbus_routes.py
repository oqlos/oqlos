"""Modbus wizard and Waveshare diagnose HTTP routes."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Body

from oqlos.api.hardware_gateway import get_hardware_gateway
from oqlos.api.hardware_modbus_waveshare import _build_waveshare_diagnose_report
from oqlos.api.hardware_modbus_wizard import (
    _modbus_wizard_plan,
    _modbus_wizard_probe_isolated,
    _modbus_wizard_program_isolated,
)
from oqlos.config import get_settings

_settings = get_settings()
router = APIRouter(tags=["hardware-modbus"])


@router.get("/modbus/waveshare-diagnose")
async def hardware_modbus_waveshare_diagnose() -> dict[str, Any]:
    """Run Waveshare-focused Modbus scan matrix and per-slave register checks."""
    health = await get_hardware_gateway().health()
    return await asyncio.to_thread(_build_waveshare_diagnose_report, health)


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
    serial = serial_port or str(_settings.modbus_serial_port)
    scan_bauds = baudrates or [9600, 4800, 19200, 38400, 57600, 115200]
    scan_parities = [str(value).upper() for value in (parities or ["N", "E", "O"])]
    scan_ids = device_ids or [1, 2, 3, 4, 5, 8, 16, 32, 64, 128, 247]
    role = str(module_role or "").strip()
    required_roles = [role] if role in {"modbus-io", "modbus-adc"} else None
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
) -> dict[str, Any]:
    """Program one isolated module (address + UART), then verify config."""
    serial = serial_port or str(_settings.modbus_serial_port)
    return await asyncio.to_thread(
        _modbus_wizard_program_isolated,
        serial_port=serial,
        current_device_id=int(current_device_id),
        new_device_id=int(new_device_id),
        new_baudrate=int(new_baudrate),
        new_parity=str(new_parity).upper(),
        confirm_isolated=bool(confirm_isolated),
    )
