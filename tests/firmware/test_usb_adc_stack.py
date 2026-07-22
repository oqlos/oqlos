from __future__ import annotations

import pytest

from oqlos.hardware.usb_adc_stack import UsbAdcStackError, normalize_usb_adc_channels


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


def test_normalize_usb_adc_channels_rejects_payload_without_readings():
    with pytest.raises(UsbAdcStackError, match="no usable ADC channels"):
        normalize_usb_adc_channels([{"logical_name": "ai01", "reading": {}}])
