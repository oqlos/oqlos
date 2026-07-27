"""CPU temperature and sensor read routes for the hardware API."""

from __future__ import annotations

import asyncio
import pathlib
import subprocess
import time
from typing import Any

from fastapi import APIRouter, Query

from oqlos.api.hardware_gateway import get_hardware_gateway
from oqlos.config import get_settings
from oqlos.errors import OqlosError
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
    "cached": False,
    "sample_age_ms": None,
}
_USB_ADC_SAMPLE_CACHE: dict[str, Any] = {
    "channels": None,
    "sampled_at": 0.0,
    "refresh_task": None,
    "sampler_task": None,
    "active_until": 0.0,
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


def unavailable_usb_sensor_entry(sensor_id: str) -> dict[str, Any]:
    """Missing channel while USB ADC is the active telemetry source."""
    return {
        "sensor_id": sensor_id,
        "value": None,
        "ok": False,
        "error": "USB ADC channel unavailable",
        "source": "usb-adc-stack",
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
    """Read requested AI channels using a bounded stale-while-revalidate cache."""
    if _configured_adc_source() == "modbus-adc":
        return None

    now = time.monotonic()
    settings = get_settings()
    sample_interval = settings.usb_adc_sample_interval_seconds
    max_stale = max(settings.usb_adc_max_stale_seconds, sample_interval)
    cached_channels = _USB_ADC_SAMPLE_CACHE.get("channels")
    sampled_at = float(_USB_ADC_SAMPLE_CACHE.get("sampled_at", 0.0))
    sample_age = max(0.0, now - sampled_at)

    if isinstance(cached_channels, dict) and sample_age <= sample_interval:
        _ensure_usb_adc_sampler(now, max_stale)
        _USB_ADC_STATUS.update(cached=True, sample_age_ms=round(sample_age * 1000, 1))
        return _requested_usb_channels(sensor_ids, cached_channels)

    if isinstance(cached_channels, dict) and sample_age <= max_stale:
        _ensure_usb_adc_sampler(now, max_stale)
        _USB_ADC_STATUS.update(cached=True, sample_age_ms=round(sample_age * 1000, 1))
        return _requested_usb_channels(sensor_ids, cached_channels)

    if (
        _USB_ADC_STATUS.get("available") is False
        and now < float(_USB_ADC_STATUS.get("retry_after", 0.0))
    ):
        return None

    refresh_task = _USB_ADC_SAMPLE_CACHE.get("refresh_task")
    if not isinstance(refresh_task, asyncio.Task) or refresh_task.done():
        refresh_task = asyncio.create_task(_refresh_usb_adc_sample())
        _USB_ADC_SAMPLE_CACHE["refresh_task"] = refresh_task
    await refresh_task
    _ensure_usb_adc_sampler(time.monotonic(), max_stale)
    refreshed_channels = _USB_ADC_SAMPLE_CACHE.get("channels")
    if not isinstance(refreshed_channels, dict):
        return None
    refreshed_at = float(_USB_ADC_SAMPLE_CACHE.get("sampled_at", 0.0))
    refreshed_age = max(0.0, time.monotonic() - refreshed_at)
    if refreshed_age > max_stale:
        return None
    _USB_ADC_STATUS.update(cached=False, sample_age_ms=round(refreshed_age * 1000, 1))
    return _requested_usb_channels(sensor_ids, refreshed_channels)


def _ensure_usb_adc_sampler(now: float, keep_alive_seconds: float) -> None:
    """Keep one sampler active while telemetry clients are polling."""
    _USB_ADC_SAMPLE_CACHE["active_until"] = max(
        float(_USB_ADC_SAMPLE_CACHE.get("active_until", 0.0)),
        now + keep_alive_seconds,
    )
    sampler_task = _USB_ADC_SAMPLE_CACHE.get("sampler_task")
    if not isinstance(sampler_task, asyncio.Task) or sampler_task.done():
        _USB_ADC_SAMPLE_CACHE["sampler_task"] = asyncio.create_task(
            _run_usb_adc_sampler()
        )


async def _run_usb_adc_sampler() -> None:
    """Refresh at the configured cadence without overlapping physical reads."""
    try:
        settings = get_settings()
        sampled_at = float(_USB_ADC_SAMPLE_CACHE.get("sampled_at", 0.0))
        delay = max(
            0.0,
            settings.usb_adc_sample_interval_seconds
            - (time.monotonic() - sampled_at),
        )
        while time.monotonic() < float(_USB_ADC_SAMPLE_CACHE.get("active_until", 0.0)):
            settings = get_settings()
            now = time.monotonic()
            retry_after = float(_USB_ADC_STATUS.get("retry_after", 0.0))
            if _USB_ADC_STATUS.get("available") is False:
                delay = max(delay, retry_after - now)
            if delay > 0:
                await asyncio.sleep(delay)
            if time.monotonic() >= float(
                _USB_ADC_SAMPLE_CACHE.get("active_until", 0.0)
            ):
                break
            refresh_started = time.monotonic()
            await _refresh_usb_adc_sample()
            refresh_duration = time.monotonic() - refresh_started
            # Cadence is start-to-start. If the hardware read itself exceeds
            # the target period, continue immediately but never overlap reads.
            delay = max(
                0.0,
                settings.usb_adc_sample_interval_seconds - refresh_duration,
            )
    finally:
        _USB_ADC_SAMPLE_CACHE["sampler_task"] = None


def _requested_usb_channels(
    sensor_ids: list[str],
    channels: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]] | None:
    requested: dict[str, dict[str, Any]] = {}
    for sensor_id in sensor_ids:
        channel = channels.get(_adc_channel_key(sensor_id))
        if channel is not None:
            requested[sensor_id] = {**channel, "sensor_id": sensor_id}
    return requested or None


async def _refresh_usb_adc_sample() -> None:
    """Perform one physical sidecar read and atomically publish its sample."""
    now = time.monotonic()
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
            cached=isinstance(_USB_ADC_SAMPLE_CACHE.get("channels"), dict),
        )
        return

    sampled_at = time.monotonic()
    _USB_ADC_SAMPLE_CACHE.update(channels=channels, sampled_at=sampled_at)
    _USB_ADC_STATUS.update(
        available=True,
        error=None,
        retry_after=0.0,
        cached=False,
        sample_age_ms=0.0,
    )


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


def fresh_gateway_health() -> dict[str, Any] | None:
    """Return cached health without triggering plugin probes."""
    cached = _BATCH_HEALTH_CACHE.get("payload")
    if (
        isinstance(cached, dict)
        and time.monotonic() < float(_BATCH_HEALTH_CACHE.get("expires_at", 0))
    ):
        return cached
    return None


async def read_sensor_values(
    sensor_ids: list[str],
    *,
    health: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    usb_sensors = await read_usb_adc_sensor_values(sensor_ids)
    if usb_sensors is not None:
        if len(usb_sensors) == len(sensor_ids):
            return usb_sensors
        # USB stack is active for this batch — do not blame the disabled Modbus ADC
        # plugin for channels the sidecar omitted or reported as failed.
        return {
            sensor_id: usb_sensors.get(sensor_id) or unavailable_usb_sensor_entry(sensor_id)
            for sensor_id in sensor_ids
        }

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
        raise OqlosError(
            code="modbus_adc_not_detected",
            status_code=503,
            message="Modbus ADC is not available for real sensor readings",
            detail={"sensor_id": sensor_id, "modbus_adc": modbus_adc_health},
        )

    value = await get_hardware_gateway().read_sensor(sensor_id)
    return {"sensor_id": sensor_id, "value": value}


@router.get("/temperature")
async def hardware_temperature() -> dict[str, Any]:
    """Read CPU temperature, returning an HUI-compatible unavailable payload if absent.

    Soft telemetry stays HTTP 200: HUI polls this endpoint and treats it as
    non-fatal. Unavailable readings carry diagnostics.issue_code for catalog
    alignment without raising Problem Details.
    """
    temp_data = read_cpu_temperature()
    available = bool(temp_data["available"])
    payload: dict[str, Any] = {
        "ok": available,
        "peripheral_id": "cpu-temperature",
        "command": "read_temperature",
        "result": {
            "success": available,
            "data": temp_data,
        },
    }
    if not available:
        payload["error"] = "Temperature sensor not available"
        payload["diagnostics"] = {"issue_code": "config_unavailable"}
        payload["code"] = payload["error_code"] = "C2004-HW-0012"
    return payload


@router.get("/sensors/batch")
async def read_sensors_batch(
    sensor_ids: str = Query(
        default="ai01,ai02,ai03",
        description="Comma-separated sensor IDs",
    ),
) -> dict[str, Any]:
    """Read multiple sensors without making HUI fall back to repeated failing requests."""
    ids = [sensor_id.strip() for sensor_id in sensor_ids.split(",") if sensor_id.strip()]
    # The preferred USB ADC sidecar is independent of plugin health.  Probing
    # every plugin before each high-frequency telemetry read caused periodic multi-
    # second stalls whenever the 3 s health cache expired.  Pass only a fresh
    # cached value; read_sensor_values obtains live health itself if it needs
    # to fall back to Modbus or fill a partial USB batch.
    health = fresh_gateway_health()
    sensors = await read_sensor_values(ids, health=health)
    health = fresh_gateway_health() or {"mode": get_settings().hardware_mode}
    modbus_unavailable, modbus_adc_health = modbus_adc_unavailable(health)
    successful = sum(1 for sensor in sensors.values() if sensor.get("ok"))
    complete = bool(sensors) and successful == len(sensors)
    diagnostics = {
        "mode": health.get("mode"),
        "adc_source": (
            "usb-adc-stack"
            if _USB_ADC_STATUS.get("available") is True
            else "modbus-adc"
        ),
        "usb_adc_stack": {
            "available": _USB_ADC_STATUS.get("available"),
            "error": _USB_ADC_STATUS.get("error"),
            "cached": _USB_ADC_STATUS.get("cached"),
            "sample_age_ms": _USB_ADC_STATUS.get("sample_age_ms"),
            "target_interval_ms": round(
                get_settings().usb_adc_sample_interval_seconds * 1000
            ),
            "max_stale_ms": round(get_settings().usb_adc_max_stale_seconds * 1000),
        },
        **({"modbus_adc": modbus_adc_health} if modbus_unavailable else {}),
    }

    # Complete transport loss → typed Problem Details. Partial channel failures
    # (sidecar up, some AI channels timed out) stay in the 200 payload.
    if ids and successful == 0 and (
        _USB_ADC_STATUS.get("available") is False or modbus_unavailable
    ):
        usb_down = _USB_ADC_STATUS.get("available") is False
        if usb_down:
            raise OqlosError(
                code="hw_usb_adc_sidecar_unreachable",
                status_code=503,
                message=str(
                    _USB_ADC_STATUS.get("error") or "USB ADC sidecar unavailable"
                ),
                detail={"sensors": sensors, "diagnostics": diagnostics},
            )
        raise OqlosError(
            code="modbus_adc_not_detected",
            status_code=503,
            message="Modbus ADC is not available for real sensor readings",
            detail={"sensors": sensors, "diagnostics": diagnostics},
        )

    return {
        # A telemetry batch is usable when at least one independent sensor
        # transport responded. Individual channel failures stay explicit in
        # the payload instead of failing the entire HUI process.
        "ok": successful > 0,
        "complete": complete,
        "degraded": successful > 0 and not complete,
        "sensors": sensors,
        "diagnostics": diagnostics,
    }


@router.get("/diagnose")
async def hardware_diagnose() -> dict[str, Any]:
    """Return HUI-friendly hardware diagnostics without failing the request."""
    try:
        health = await cached_gateway_health(force=True)
    except Exception as exc:
        raise OqlosError(
            code="config_unavailable",
            status_code=503,
            message=f"Hardware gateway health unavailable: {exc}",
            detail={"error": str(exc)},
        ) from exc

    sensors = await read_sensor_values(list(DEFAULT_BATCH_SENSOR_IDS), health=health)
    return {
        "ok": True,
        "gateway_mode": health.get("mode", "unknown"),
        "gateway_health": health,
        "sensors": sensors,
    }
