"""Tests for Modbus identify enrichment."""

from __future__ import annotations

from oqlos.hardware.modbus_identify import enrich_modbus_identify, enrich_platform_modbus_ports


def test_enrich_platform_modbus_ports_from_serial_list() -> None:
    payload = {
        "platform": {
            "modbus_io_serial_port": "",
            "serial_ports": ["/dev/ttyACM0", "/dev/ttyACM1"],
        },
    }

    out = enrich_platform_modbus_ports(payload)

    assert out["platform"]["modbus_io_serial_port"] == "/dev/ttyACM1"


def test_enrich_modbus_serial_hints_on_modbus_io() -> None:
    payload = {
        "adapters": [{"id": "modbus-io", "status": "adapter-only", "probe": {"connected": False}}],
        "diagnostics": {
            "usb_devices": [
                {
                    "vendor_id": "1a86",
                    "product_id": "7523",
                    "manufacturer": "QinHeng",
                    "product": "USB Single Serial",
                },
            ],
        },
    }

    out = enrich_modbus_identify(payload)

    probe = next(a for a in out["adapters"] if a["id"] == "modbus-io")["probe"]
    assert len(probe["serial_candidates"]) == 1
    assert "hint" in probe
