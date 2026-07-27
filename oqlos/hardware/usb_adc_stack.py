"""Client and payload normalization for the local USB/UART ADC sidecar."""

from __future__ import annotations

import math
from typing import Any

import httpx


class UsbAdcStackError(RuntimeError):
    """Raised when the ADC sidecar cannot provide a valid channel payload."""


def normalize_usb_adc_channels(payload: Any) -> dict[str, dict[str, Any]]:
    """Convert ``usb-adc-stack`` readings to the OqlOS sensor contract."""
    if not isinstance(payload, list):
        raise UsbAdcStackError("usb-adc-stack returned a non-list ADC payload")

    channels: dict[str, dict[str, Any]] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        sensor_id = str(item.get("logical_name") or "").strip().lower()
        if not sensor_id.startswith("ai"):
            continue

        reading = item.get("reading")
        if isinstance(reading, dict):
            try:
                volts = float(reading["volts"])
            except (KeyError, TypeError, ValueError):
                volts = None
            if volts is not None and math.isfinite(volts):
                channels[sensor_id] = {
                    "sensor_id": sensor_id,
                    "value": volts,
                    "ok": True,
                    "unit": "V",
                    "source": "usb-adc-stack",
                    "adapter": item.get("adapter"),
                    "physical_input": item.get("physical_input"),
                    "details": reading,
                }
                continue

        error = item.get("error")
        if item.get("ok") is False or error:
            channels[sensor_id] = {
                "sensor_id": sensor_id,
                "value": None,
                "ok": False,
                "error": str(error or "USB ADC channel unavailable"),
                "source": "usb-adc-stack",
                "adapter": item.get("adapter"),
                "physical_input": item.get("physical_input"),
            }

    if not channels:
        raise UsbAdcStackError("usb-adc-stack returned no usable ADC channels")
    return channels


async def read_usb_adc_channels(
    base_url: str,
    *,
    timeout_seconds: float = 0.8,
) -> dict[str, dict[str, Any]]:
    """Read all logical ADC inputs exposed by the local sidecar."""
    url = f"{base_url.rstrip('/')}/api/v1/adc"
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(url)
            response.raise_for_status()
            return normalize_usb_adc_channels(response.json())
    except UsbAdcStackError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise UsbAdcStackError(f"usb-adc-stack request failed: {exc}") from exc
