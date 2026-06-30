"""Regression: modbus-io virtual adapter expansion."""

from __future__ import annotations

from oqlos.hardware.client.identify_enrich_modbus_io import expand_modbus_io_instances


def test_expand_modbus_io_instances_clones_per_slave_id(monkeypatch):
    monkeypatch.setenv("OQLOS_MODBUS_IO_DEVICE_IDS", "1,2")

    adapters = [
        {
            "id": "modbus-io",
            "name": "Waveshare Modbus RTU IO 8CH",
            "status": "ok",
            "probe": {"local_probe": {"device_id": 1}},
        }
    ]

    expanded = expand_modbus_io_instances(adapters, {"diagnostics": {}})

    assert [entry["id"] for entry in expanded] == ["modbus-io-1", "modbus-io-2"]
    assert expanded[1]["name"].endswith("(slave 2)")
