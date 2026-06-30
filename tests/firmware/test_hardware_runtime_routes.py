"""Regression tests for extracted runtime sensor routes."""

from __future__ import annotations

import asyncio

from oqlos.api import hardware as hw
from oqlos.api import hardware_runtime as runtime


def test_hardware_router_includes_runtime_paths():
    paths = {route.path for route in hw.router.routes}
    assert "/api/v1/hardware/sensor/{sensor_id}" in paths
    assert "/api/v1/hardware/temperature" in paths
    assert "/api/v1/hardware/sensors/batch" in paths
    assert "/api/v1/hardware/diagnose" in paths


def test_modbus_adc_unavailable_detects_incompatible_adc():
    health = {
        "mode": "real",
        "modbus-adc": {"compatible": False, "status": "error"},
    }
    unavailable, adc = runtime.modbus_adc_unavailable(health)
    assert unavailable is True
    assert adc["status"] == "error"


class _UnavailableAdcGateway:
    async def health(self):
        return {
            "mode": "real",
            "modbus-adc": {"compatible": False, "status": "error"},
        }

    async def read_sensor(self, sensor_id: str):
        raise AssertionError(sensor_id)


def test_read_sensor_values_skips_live_reads_when_adc_unavailable():
    sensors = asyncio.run(
        runtime.read_sensor_values(
            ["ai01"],
            health={
                "mode": "real",
                "modbus-adc": {"compatible": False},
            },
        )
    )
    assert sensors["ai01"]["ok"] is False
    assert sensors["ai01"]["value"] is None
