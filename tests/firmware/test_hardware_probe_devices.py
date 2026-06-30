"""Regression: hardware_probe device helpers stay importable from hardware_probe."""

from __future__ import annotations

from oqlos.api import hardware_probe as hw_probe
from oqlos.api import hardware_probe_devices as devices


def test_hardware_probe_reexports_device_helpers():
    for name in (
        "_scan_usb_devices",
        "_probe_tic249",
        "_probe_dri0050",
        "_probe_i2c_ads1115",
        "_probe_configured_waveshare_rtu",
    ):
        assert hasattr(hw_probe, name)
        assert getattr(hw_probe, name) is getattr(devices, name)


def test_probe_tic249_detects_vendor_product():
    result = devices._probe_tic249(
        [{"vendor_id": "1ffb", "product_id": "00c9", "product": "Tic", "serial": "abc", "path": "/x"}]
    )
    assert result["connected"] is True
    assert result["usb_product"] == "Tic"
