"""Client and payload normalization for the local USB/UART ADC sidecar."""

from __future__ import annotations

import asyncio
import math
from typing import Any

import httpx


class UsbAdcStackError(RuntimeError):
    """Raised when the ADC sidecar cannot provide a valid channel payload."""


_USB_ADC_HTTP_CLIENT: dict[str, Any] = {
    "loop": None,
    "base_url": None,
    "timeout_seconds": None,
    "client": None,
}


def _usb_adc_http_client(base_url: str, timeout_seconds: float) -> httpx.AsyncClient:
    """Reuse the loopback connection for high-frequency telemetry reads."""
    loop = asyncio.get_running_loop()
    normalized_base_url = base_url.rstrip("/")
    client = _USB_ADC_HTTP_CLIENT.get("client")
    if (
        isinstance(client, httpx.AsyncClient)
        and not client.is_closed
        and _USB_ADC_HTTP_CLIENT.get("loop") is loop
        and _USB_ADC_HTTP_CLIENT.get("base_url") == normalized_base_url
        and _USB_ADC_HTTP_CLIENT.get("timeout_seconds") == timeout_seconds
    ):
        return client

    client = httpx.AsyncClient(
        base_url=normalized_base_url,
        timeout=timeout_seconds,
        limits=httpx.Limits(max_connections=2, max_keepalive_connections=1),
    )
    _USB_ADC_HTTP_CLIENT.update(
        loop=loop,
        base_url=normalized_base_url,
        timeout_seconds=timeout_seconds,
        client=client,
    )
    return client


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
    client = _usb_adc_http_client(base_url, timeout_seconds)
    try:
        response = await client.get("/api/v1/adc")
        response.raise_for_status()
        return normalize_usb_adc_channels(response.json())
    except UsbAdcStackError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise UsbAdcStackError(f"usb-adc-stack request failed: {exc}") from exc
