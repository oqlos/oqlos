"""CPU temperature and sensor read routes for the hardware API."""

from __future__ import annotations

import pathlib
import subprocess
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from oqlos.api.hardware_gateway import get_hardware_gateway

router = APIRouter(tags=["hardware-runtime"])

DEFAULT_BATCH_SENSOR_IDS = ("ai01", "ai02", "ai03")


def read_cpu_temperature() -> dict[str, Any]:
    """Best-effort CPU temperature read for HUI status panels."""
    thermal_paths = [
        pathlib.Path("/sys/class/thermal/thermal_zone0/temp"),
        *sorted(pathlib.Path("/sys/class/thermal").glob("thermal_zone*/temp")),
    ]
    seen: set[pathlib.Path] = set()
    for path in thermal_paths:
        if path in seen:
            continue
        seen.add(path)
        try:
            raw = path.read_text(encoding="utf-8").strip()
            if not raw:
                continue
            temp_millidegrees = float(raw)
        except (OSError, ValueError):
            continue
        return {
            "cpu_temp_celsius": round(temp_millidegrees / 1000, 1),
            "source": str(path),
            "available": True,
        }
    try:
        output = subprocess.run(
            ["vcgencmd", "measure_temp"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if output.returncode == 0:
            temp_text = output.stdout.strip()
            if "temp=" in temp_text:
                temp_value = temp_text.split("temp=", 1)[1].split("'", 1)[0]
                return {
                    "cpu_temp_celsius": round(float(temp_value), 1),
                    "source": "vcgencmd",
                    "available": True,
                }
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return {
        "cpu_temp_celsius": None,
        "source": None,
        "available": False,
    }


def modbus_adc_unavailable(health: dict[str, Any]) -> tuple[bool, Any]:
    modbus_adc_health = health.get("modbus-adc")
    unavailable = (
        health.get("mode") == "real"
        and isinstance(modbus_adc_health, dict)
        and not modbus_adc_health.get("compatible")
    )
    return unavailable, modbus_adc_health


def unavailable_sensor_entry(sensor_id: str, modbus_adc_health: Any) -> dict[str, Any]:
    return {
        "sensor_id": sensor_id,
        "value": None,
        "ok": False,
        "error": "Modbus ADC is not available for real sensor readings",
        "modbus_adc": modbus_adc_health,
    }


async def read_sensor_values(
    sensor_ids: list[str],
    *,
    health: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    gateway_health = health if health is not None else await get_hardware_gateway().health()
    modbus_unavailable, modbus_adc_health = modbus_adc_unavailable(gateway_health)

    sensors: dict[str, dict[str, Any]] = {}
    for sensor_id in sensor_ids:
        if modbus_unavailable:
            sensors[sensor_id] = unavailable_sensor_entry(sensor_id, modbus_adc_health)
            continue
        try:
            value = await get_hardware_gateway().read_sensor(sensor_id)
            sensors[sensor_id] = {
                "sensor_id": sensor_id,
                "value": value,
                "ok": value is not None,
            }
        except Exception as exc:
            sensors[sensor_id] = {
                "sensor_id": sensor_id,
                "value": None,
                "ok": False,
                "error": str(exc),
            }
    return sensors


@router.get("/sensor/{sensor_id}")
async def read_sensor(sensor_id: str):
    """Read a sensor value directly from hardware."""
    health = await get_hardware_gateway().health()
    modbus_unavailable, modbus_adc_health = modbus_adc_unavailable(health)
    if modbus_unavailable:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Modbus ADC is not available for real sensor readings",
                "sensor_id": sensor_id,
                "modbus_adc": modbus_adc_health,
            },
        )

    value = await get_hardware_gateway().read_sensor(sensor_id)
    return {"sensor_id": sensor_id, "value": value}


@router.get("/temperature")
async def hardware_temperature() -> dict[str, Any]:
    """Read CPU temperature, returning an HUI-compatible unavailable payload if absent."""
    temp_data = read_cpu_temperature()
    return {
        "ok": bool(temp_data["available"]),
        "peripheral_id": "cpu-temperature",
        "command": "read_temperature",
        **({"error": "Temperature sensor not available"} if not temp_data["available"] else {}),
        "result": {
            "success": bool(temp_data["available"]),
            "data": temp_data,
        },
    }


@router.get("/sensors/batch")
async def read_sensors_batch(
    sensor_ids: str = Query(
        default="ai01,ai02,ai03",
        description="Comma-separated sensor IDs",
    ),
) -> dict[str, Any]:
    """Read multiple sensors without making HUI fall back to repeated failing requests."""
    ids = [sensor_id.strip() for sensor_id in sensor_ids.split(",") if sensor_id.strip()]
    health = await get_hardware_gateway().health()
    modbus_unavailable, modbus_adc_health = modbus_adc_unavailable(health)
    sensors = await read_sensor_values(ids, health=health)

    return {
        "ok": all(sensor.get("ok") for sensor in sensors.values()) if sensors else False,
        "sensors": sensors,
        "diagnostics": {
            "mode": health.get("mode"),
            **({"modbus_adc": modbus_adc_health} if modbus_unavailable else {}),
        },
    }


@router.get("/diagnose")
async def hardware_diagnose() -> dict[str, Any]:
    """Return HUI-friendly hardware diagnostics without failing the request."""
    try:
        health = await get_hardware_gateway().health()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    sensors = await read_sensor_values(list(DEFAULT_BATCH_SENSOR_IDS), health=health)
    return {
        "ok": True,
        "gateway_mode": health.get("mode", "unknown"),
        "gateway_health": health,
        "sensors": sensors,
    }
