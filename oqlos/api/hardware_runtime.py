"""CPU temperature and sensor read routes for the hardware API."""

from __future__ import annotations

import pathlib
import subprocess
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from oqlos.api.hardware_gateway import get_hardware_gateway
from oqlos.config import get_settings
from oqlos.hardware.client.adc import adc_sensor_alias
from oqlos.hardware.usb_adc_stack import UsbAdcStackError, read_usb_adc_channels

router = APIRouter(tags=["hardware-runtime"])

DEFAULT_BATCH_SENSOR_IDS = ("ai01", "ai02", "ai03")
BATCH_HEALTH_TTL_SEC = 3.0
_BATCH_HEALTH_CACHE: dict[str, Any] = {"expires_at": 0.0, "payload": None}
USB_ADC_FAILURE_TTL_SEC = 3.0
_USB_ADC_STATUS: dict[str, Any] = {
    "available": None,
    "error": None,
    "retry_after": 0.0,
}


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


def _adc_channel_key(sensor_id: str) -> str:
    _, oqlos_sensor_id = adc_sensor_alias(sensor_id)
    return oqlos_sensor_id


def _sensor_entry_from_channel(sensor_id: str, channel: Any) -> dict[str, Any]:
    if isinstance(channel, dict):
        value = channel.get("value")
        return {
            "sensor_id": sensor_id,
            "value": value,
            "ok": value is not None,
            **({"details": channel} if channel.get("raw") is not None else {}),
        }
    return {
        "sensor_id": sensor_id,
        "value": channel,
        "ok": channel is not None,
    }


def _configured_adc_source() -> str:
    source = str(get_settings().adc_source or "auto").strip().lower()
    return source if source in {"auto", "usb-adc-stack", "modbus-adc"} else "auto"


async def read_usb_adc_sensor_values(
    sensor_ids: list[str],
) -> dict[str, dict[str, Any]] | None:
    """Read requested AI channels from the sidecar, with a short failure backoff."""
    if _configured_adc_source() == "modbus-adc":
        return None

    now = time.monotonic()
    if (
        _USB_ADC_STATUS.get("available") is False
        and now < float(_USB_ADC_STATUS.get("retry_after", 0.0))
    ):
        return None

    settings = get_settings()
    try:
        channels = await read_usb_adc_channels(
            settings.usb_adc_stack_url,
            timeout_seconds=settings.usb_adc_timeout_seconds,
        )
    except UsbAdcStackError as exc:
        _USB_ADC_STATUS.update(
            available=False,
            error=str(exc),
            retry_after=now + USB_ADC_FAILURE_TTL_SEC,
        )
        return None

    _USB_ADC_STATUS.update(available=True, error=None, retry_after=0.0)
    requested: dict[str, dict[str, Any]] = {}
    for sensor_id in sensor_ids:
        channel = channels.get(_adc_channel_key(sensor_id))
        if channel is not None:
            requested[sensor_id] = {**channel, "sensor_id": sensor_id}
    return requested if len(requested) == len(sensor_ids) else None


async def cached_gateway_health(*, force: bool = False) -> dict[str, Any]:
    """Short-lived health cache so polling endpoints do not probe every plugin each tick."""
    now = time.monotonic()
    cached = _BATCH_HEALTH_CACHE.get("payload")
    if (
        not force
        and isinstance(cached, dict)
        and now < float(_BATCH_HEALTH_CACHE.get("expires_at", 0))
    ):
        return cached

    payload = await get_hardware_gateway().health()
    _BATCH_HEALTH_CACHE["payload"] = payload
    _BATCH_HEALTH_CACHE["expires_at"] = now + BATCH_HEALTH_TTL_SEC
    return payload


async def read_sensor_values(
    sensor_ids: list[str],
    *,
    health: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    usb_sensors = await read_usb_adc_sensor_values(sensor_ids)
    if usb_sensors is not None:
        return usb_sensors

    gateway_health = health if health is not None else await cached_gateway_health()
    modbus_unavailable, modbus_adc_health = modbus_adc_unavailable(gateway_health)

    if modbus_unavailable:
        return {
            sensor_id: unavailable_sensor_entry(sensor_id, modbus_adc_health)
            for sensor_id in sensor_ids
        }

    gateway = get_hardware_gateway()
    read_adc_channels = getattr(gateway, "read_adc_channels", None)
    if callable(read_adc_channels):
        channel_keys = [_adc_channel_key(sensor_id) for sensor_id in sensor_ids]
        if channel_keys and all(key.startswith("ai") for key in channel_keys):
            channels = await read_adc_channels()
            if isinstance(channels, dict):
                return {
                    sensor_id: _sensor_entry_from_channel(sensor_id, channels.get(channel_key))
                    for sensor_id, channel_key in zip(sensor_ids, channel_keys, strict=True)
                }

    sensors: dict[str, dict[str, Any]] = {}
    for sensor_id in sensor_ids:
        try:
            value = await gateway.read_sensor(sensor_id)
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
    usb_sensors = await read_usb_adc_sensor_values([sensor_id])
    if usb_sensors is not None:
        return usb_sensors[sensor_id]

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
    health = await cached_gateway_health()
    modbus_unavailable, modbus_adc_health = modbus_adc_unavailable(health)
    sensors = await read_sensor_values(ids, health=health)

    return {
        "ok": all(sensor.get("ok") for sensor in sensors.values()) if sensors else False,
        "sensors": sensors,
        "diagnostics": {
            "mode": health.get("mode"),
            "adc_source": (
                "usb-adc-stack"
                if _USB_ADC_STATUS.get("available") is True
                else "modbus-adc"
            ),
            "usb_adc_stack": {
                "available": _USB_ADC_STATUS.get("available"),
                "error": _USB_ADC_STATUS.get("error"),
            },
            **({"modbus_adc": modbus_adc_health} if modbus_unavailable else {}),
        },
    }


@router.get("/diagnose")
async def hardware_diagnose() -> dict[str, Any]:
    """Return HUI-friendly hardware diagnostics without failing the request."""
    try:
        health = await cached_gateway_health(force=True)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    sensors = await read_sensor_values(list(DEFAULT_BATCH_SENSOR_IDS), health=health)
    return {
        "ok": True,
        "gateway_mode": health.get("mode", "unknown"),
        "gateway_health": health,
        "sensors": sensors,
    }
