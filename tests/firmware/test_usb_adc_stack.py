from __future__ import annotations

import pytest

from oqlos.hardware.usb_adc_stack import (
    UsbAdcStackError,
    _USB_ADC_HTTP_CLIENT,
    _usb_adc_http_client,
    normalize_usb_adc_channels,
    read_usb_adc_health,
)


def test_normalize_usb_adc_channels_preserves_voltage_and_source_metadata():
    channels = normalize_usb_adc_channels(
        [
            {
                "logical_name": "ai01",
                "adapter": "usb-adc-mcp2221",
                "physical_input": "MCP2221A.G1",
                "reading": {"volts": 1.25, "raw_10bit": 388},
            },
            {
                "logical_name": "ai02",
                "adapter": "usb-adc-dfr1184",
                "physical_input": "DFR1184.AIN1",
                "reading": {"volts": 4.5, "raw_hundredth_millivolts": 450000},
            },
        ]
    )

    assert channels["ai01"]["value"] == 1.25
    assert channels["ai01"]["unit"] == "V"
    assert channels["ai01"]["source"] == "usb-adc-stack"
    assert channels["ai02"]["adapter"] == "usb-adc-dfr1184"


def test_normalize_usb_adc_channels_keeps_failed_sidecar_channels():
    channels = normalize_usb_adc_channels(
        [
            {
                "logical_name": "ai01",
                "adapter": "usb-adc-mcp2221",
                "physical_input": "MCP2221A.G1",
                "reading": {"volts": 1.25},
            },
            {
                "logical_name": "ai02",
                "adapter": "usb-adc-dfr1184",
                "physical_input": "DFR1184.AIN1",
                "ok": False,
                "error": "usb-adc-dfr1184 read timed out after 2.5s",
            },
        ]
    )

    assert channels["ai01"]["ok"] is True
    assert channels["ai02"] == {
        "sensor_id": "ai02",
        "value": None,
        "ok": False,
        "error": "usb-adc-dfr1184 read timed out after 2.5s",
        "source": "usb-adc-stack",
        "adapter": "usb-adc-dfr1184",
        "physical_input": "DFR1184.AIN1",
    }


def test_normalize_usb_adc_channels_rejects_payload_without_readings():
    with pytest.raises(UsbAdcStackError, match="no usable ADC channels"):
        normalize_usb_adc_channels([{"logical_name": "ai01", "reading": {}}])


@pytest.mark.asyncio
async def test_usb_adc_http_client_reuses_same_loopback_pool():
    _USB_ADC_HTTP_CLIENT.update(
        loop=None,
        base_url=None,
        timeout_seconds=None,
        client=None,
    )

    first = _usb_adc_http_client("http://127.0.0.1:8214/", 0.8)
    second = _usb_adc_http_client("http://127.0.0.1:8214", 0.8)

    assert first is second
    await first.aclose()


@pytest.mark.asyncio
async def test_read_usb_adc_health_requires_component_payload(monkeypatch):
    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": False, "components": {"usb-adc-dfr1184": {"ok": False}}}

    class _Client:
        async def get(self, path):
            assert path == "/health"
            return _Response()

    monkeypatch.setattr(
        "oqlos.hardware.usb_adc_stack._usb_adc_http_client",
        lambda _base_url, _timeout: _Client(),
    )

    payload = await read_usb_adc_health("http://127.0.0.1:8214")

    assert payload["components"]["usb-adc-dfr1184"]["ok"] is False
