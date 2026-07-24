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


class _BatchAdcGateway:
    read_sensor_calls = 0
    read_all_calls = 0

    async def health(self):
        return {"mode": "real", "modbus-adc": {"compatible": True, "status": "connected"}}

    async def read_adc_channels(self):
        type(self).read_all_calls += 1
        return {
            "ai01": {"sensor_id": "ai01", "value": 7901.0, "raw": 7901},
            "ai02": {"sensor_id": "ai02", "value": 7893.0, "raw": 7893},
            "ai03": {"sensor_id": "ai03", "value": 8275.0, "raw": 8275},
        }

    async def read_sensor(self, sensor_id: str):
        type(self).read_sensor_calls += 1
        raise AssertionError(f"sequential read_sensor should not run in batch fast path: {sensor_id}")


def test_read_sensor_values_uses_single_adc_read_all_for_batch(monkeypatch):
    _BatchAdcGateway.read_sensor_calls = 0
    _BatchAdcGateway.read_all_calls = 0
    runtime._BATCH_HEALTH_CACHE["expires_at"] = 0.0
    runtime._BATCH_HEALTH_CACHE["payload"] = None
    gateway = _BatchAdcGateway()
    monkeypatch.setattr(runtime, "get_hardware_gateway", lambda: gateway)
    healthy = {"mode": "real", "modbus-adc": {"compatible": True, "status": "connected"}}

    sensors = asyncio.run(
        runtime.read_sensor_values(["ai01", "ai02", "ai03"], health=healthy),
    )
    assert _BatchAdcGateway.read_all_calls == 1
    assert _BatchAdcGateway.read_sensor_calls == 0
    assert sensors["ai01"]["value"] == 7901.0
    assert sensors["ai03"]["ok"] is True


def test_read_sensor_values_prefers_usb_adc_stack_over_unavailable_modbus(monkeypatch):
    async def _usb_values(sensor_ids):
        return {
            sensor_id: {
                "sensor_id": sensor_id,
                "value": index / 10,
                "unit": "V",
                "source": "usb-adc-stack",
                "ok": True,
            }
            for index, sensor_id in enumerate(sensor_ids, start=1)
        }

    monkeypatch.setattr(runtime, "read_usb_adc_sensor_values", _usb_values)
    sensors = asyncio.run(
        runtime.read_sensor_values(
            ["ai01", "ai02", "ai03"],
            health={"mode": "real", "modbus-adc": {"compatible": False}},
        )
    )

    assert sensors["ai01"]["value"] == 0.1
    assert sensors["ai03"]["unit"] == "V"
    assert sensors["ai03"]["source"] == "usb-adc-stack"


def test_read_sensor_values_preserves_partial_usb_batch(monkeypatch):
    async def _usb_values(_sensor_ids):
        return {
            "ai02": {
                "sensor_id": "ai02",
                "value": 2.4,
                "unit": "V",
                "source": "usb-adc-stack",
                "ok": True,
            },
            "ai03": {
                "sensor_id": "ai03",
                "value": 7.1,
                "unit": "V",
                "source": "usb-adc-stack",
                "ok": True,
            },
        }

    monkeypatch.setattr(runtime, "read_usb_adc_sensor_values", _usb_values)
    sensors = asyncio.run(
        runtime.read_sensor_values(
            ["ai01", "ai02", "ai03"],
            health={"mode": "real", "modbus-adc": {"compatible": False}},
        )
    )

    assert sensors["ai01"]["ok"] is False
    assert sensors["ai02"]["value"] == 2.4
    assert sensors["ai03"]["value"] == 7.1


def test_batch_marks_partial_usb_reading_as_usable_and_degraded(monkeypatch):
    async def _health(*, force=False):
        return {"mode": "real", "modbus-adc": {"compatible": False}}

    async def _sensor_values(_sensor_ids, *, health=None):
        return {
            "ai01": {"sensor_id": "ai01", "value": None, "ok": False},
            "ai02": {"sensor_id": "ai02", "value": 2.4, "ok": True},
            "ai03": {"sensor_id": "ai03", "value": 7.1, "ok": True},
        }

    monkeypatch.setattr(runtime, "cached_gateway_health", _health)
    monkeypatch.setattr(runtime, "read_sensor_values", _sensor_values)

    result = asyncio.run(runtime.read_sensors_batch("ai01,ai02,ai03"))

    assert result["ok"] is True
    assert result["complete"] is False
    assert result["degraded"] is True
