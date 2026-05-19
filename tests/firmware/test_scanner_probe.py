"""Tests for barcode scanner detection in hardware identify enrichment."""

from __future__ import annotations

from oqlos.hardware.scanner_probe import (
    BARCODE_SCANNER_ID,
    enrich_scanner_adapter,
    resolve_scanner_presence,
)


def test_scan_diagnostics_usb_ignores_crw_without_barcode_tokens(monkeypatch) -> None:
    monkeypatch.setattr("oqlos.hardware.scanner_probe._scan_lsusb_matches", lambda: [])
    monkeypatch.setattr("oqlos.hardware.scanner_probe._scan_input_matches", lambda: [])
    diagnostics = {
        "usb_devices": [
            {
                "vendor_id": "0bda",
                "product_id": "0328",
                "manufacturer": "Generic",
                "product": "USB3.0-CRW",
            },
        ],
    }

    present, detail = resolve_scanner_presence(diagnostics)

    assert present is False
    assert detail["matched_devices"] == []


def test_holtek_present_from_diagnostics_usb(monkeypatch) -> None:
    monkeypatch.setattr("oqlos.hardware.scanner_probe._scan_lsusb_matches", lambda: [])
    monkeypatch.setattr("oqlos.hardware.scanner_probe._scan_input_matches", lambda: [])
    diagnostics = {
        "usb_devices": [
            {
                "vendor_id": "04d9",
                "product_id": "a231",
                "manufacturer": "HOLTEK",
                "product": "USB-HID Keyboard",
            },
        ],
    }

    present, detail = resolve_scanner_presence(diagnostics)

    assert present is True
    assert detail["matched_devices"][0]["product"] == "USB-HID Keyboard"


def test_enrich_scanner_adapter_adds_entry(monkeypatch) -> None:
    monkeypatch.setattr(
        "oqlos.hardware.scanner_probe._scan_lsusb_matches",
        lambda: [],
    )
    monkeypatch.setattr(
        "oqlos.hardware.scanner_probe._scan_input_matches",
        lambda: [],
    )
    payload = {"adapters": [{"id": "modbus-io", "status": "ok"}], "total": 1, "detected": 1}

    out = enrich_scanner_adapter(payload)

    scanner = next(item for item in out["adapters"] if item["id"] == BARCODE_SCANNER_ID)
    assert scanner["status"] == "adapter-only"
    assert out["total"] == 2
