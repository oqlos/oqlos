"""Modbus ADC raw read and RTC sidecar routes."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Body

from oqlos.api.hardware_gateway import get_hardware_gateway
from oqlos.api.hardware_lung import command_payload
from oqlos.errors import OqlosError
from oqlos.hardware.rtc_probe import build_rtc_peripheral_status, run_rtc_command

router = APIRouter(tags=["hardware-peripherals"])


def _raise_modbus_adc_raw(
    message: str,
    *,
    detail: dict[str, Any],
    code: str = "modbus_adc_not_detected",
) -> None:
    raise OqlosError(code=code, status_code=503, message=message, detail=detail)


@router.get("/modbus-adc/raw")
async def read_modbus_adc_raw() -> dict[str, Any]:
    """Return raw Modbus ADC diagnostics for HUI troubleshooting."""
    try:
        health = await get_hardware_gateway().health()
    except Exception as exc:
        _raise_modbus_adc_raw(str(exc), detail={"error": str(exc)})

    modbus_adc_health = health.get("modbus-adc")
    if not isinstance(modbus_adc_health, dict):
        _raise_modbus_adc_raw(
            "modbus-adc health not available",
            detail={"gateway_mode": health.get("mode"), "gateway_health": health},
        )
    if not modbus_adc_health.get("compatible"):
        _raise_modbus_adc_raw(
            "modbus-adc not compatible",
            detail={
                "gateway_mode": health.get("mode"),
                "modbus_adc_health": modbus_adc_health,
            },
        )

    try:
        plugin = await get_hardware_gateway()._get_or_connect_plugin("modbus-adc")
    except Exception as exc:
        _raise_modbus_adc_raw(
            str(exc),
            detail={
                "gateway_mode": health.get("mode"),
                "modbus_adc_health": modbus_adc_health,
            },
        )
    if not plugin:
        _raise_modbus_adc_raw(
            "modbus-adc plugin not available",
            detail={
                "gateway_mode": health.get("mode"),
                "modbus_adc_health": modbus_adc_health,
            },
        )

    result = await plugin.execute_command("read_all", {})
    if not result.get("success"):
        _raise_modbus_adc_raw(
            str(result.get("error") or "Unknown error from modbus-adc plugin"),
            code="hw_modbus_no_response",
            detail={
                "gateway_mode": health.get("mode"),
                "modbus_adc_health": modbus_adc_health,
                "plugin_result": result,
            },
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
