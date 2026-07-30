"""Modbus ADC raw read and RTC sidecar routes."""

from __future__ import annotations

import asyncio
from typing import Any, NoReturn

from fastapi import APIRouter, Body

from oqlos.api.hardware_gateway import get_hardware_gateway
from oqlos.api.hardware_lung import command_payload
from oqlos.errors import OqlosError
from oqlos.hardware.rtc_probe import build_rtc_peripheral_status, run_rtc_command

router = APIRouter(tags=["hardware-peripherals"])


def _raise_modbus_adc_raw(
    *,
    stage: str,
    reason: str,
    code: str = "modbus_adc_not_detected",
    cause: Exception | None = None,
    compatible: bool | None = None,
) -> NoReturn:
    detail: dict[str, Any] = {
        "architecture": "SOA",
        "layer": "firmware",
        "component": "modbus-adc",
        "stage": stage,
        "problem_source": "hardware",
        "operation_id": "hardware.modbus-adc.raw",
        "upstream_target": "hardware-plugin://modbus-adc",
        "reason": reason,
    }
    if compatible is not None:
        detail["modbus_adc_health"] = {"compatible": compatible}
    error = OqlosError(
        code=code,
        status_code=503,
        detail=detail,
    )
    if cause is not None:
        raise error from cause
    raise error


@router.get("/modbus-adc/raw")
async def read_modbus_adc_raw() -> dict[str, Any]:
    """Return raw Modbus ADC diagnostics for HUI troubleshooting."""
    try:
        health = await get_hardware_gateway().health()
    except (OSError, RuntimeError) as exc:
        _raise_modbus_adc_raw(
            stage="gateway.health",
            reason="gateway_health_unavailable",
            cause=exc,
        )

    modbus_adc_health = health.get("modbus-adc")
    if not isinstance(modbus_adc_health, dict):
        _raise_modbus_adc_raw(
            stage="gateway.health",
            reason="plugin_health_missing",
        )
    if not modbus_adc_health.get("compatible"):
        _raise_modbus_adc_raw(
            stage="gateway.health",
            reason="plugin_incompatible",
            compatible=False,
        )

    try:
        plugin = await get_hardware_gateway()._get_or_connect_plugin("modbus-adc")
    except (OSError, RuntimeError) as exc:
        _raise_modbus_adc_raw(
            stage="plugin.connect",
            reason="plugin_connection_failed",
            cause=exc,
        )
    if not plugin:
        _raise_modbus_adc_raw(
            stage="plugin.connect",
            reason="plugin_unavailable",
        )

    result = await plugin.execute_command("read_all", {})
    if not result.get("success"):
        _raise_modbus_adc_raw(
            code="hw_modbus_no_response",
            stage="plugin.read",
            reason="read_failed",
        )

    return {
        "ok": True,
        "gateway_mode": health.get("mode"),
        "modbus_adc_config": {
            "serial_port": getattr(plugin.config, "serial_port", "unknown"),
            "baudrate": getattr(plugin.config, "baudrate", "unknown"),
            "device_id": getattr(plugin.config, "device_id", "unknown"),
        },
        "raw_data": result.get("data", {}),
    }


@router.get("/rtc/status")
async def rtc_status():
    """Return runtime status for the RTC sidecar."""
    return await asyncio.to_thread(build_rtc_peripheral_status)


@router.post("/rtc/command")
async def rtc_command(payload: dict[str, Any] = Body(default_factory=dict)):
    """Execute a diagnostic command against the RTC sidecar."""
    command, args = command_payload(payload)
    return await asyncio.to_thread(run_rtc_command, command, args)
