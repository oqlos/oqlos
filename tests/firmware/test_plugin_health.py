"""Tests for hardware plugin health semantics."""

from __future__ import annotations

import asyncio
import time

from oqlos.hardware.plugins.base import PluginConfig, PluginStatus
from oqlos.hardware.plugins.lung import LungPlugin
from oqlos.hardware.plugins.modbus import ModbusPlugin
from oqlos.hardware.plugins.modbus_adc import ModbusAdcPlugin
from oqlos.hardware.plugins.piadc import PiadcPlugin
from oqlos.hardware.plugins.registry import PluginRegistry


class _JsonResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _PiadcClient:
    async def get(self, url):
        return _JsonResponse(
            200,
            {"status": "healthy", "initialized": True, "mock_mode": True},
        )


class _UninitializedPiadcClient:
    async def get(self, url):
        return _JsonResponse(
            200,
            {
                "status": "error",
                "initialized": False,
                "mock_mode": False,
                "message": "ADS1115 probe returned invalid config register 0x0000",
            },
        )


class _FailingPiadcClient:
    async def get(self, url):
        raise RuntimeError("connection refused")


class _LungClient:
    async def get(self, url):
        if url.endswith("/health"):
            return _JsonResponse(404, {})
        if url.endswith("/api/settings"):
            return _JsonResponse(200, {"version": "0.1.13"})
        if url.endswith("/api/status"):
            return _JsonResponse(200, {"connected": False, "error": "Motor not initialized"})
        return _JsonResponse(404, {})


class _BlockingModbusClient:
    def read_coils(self, **kwargs):
        time.sleep(0.2)
        return None


class _OkModbusResult:
    function_code = 5
    registers = [101, 202, 303, 404, 505, 606, 707, 808]

    def isError(self):
        return False


class _CapturingModbusClient:
    def __init__(self):
        self.read_kwargs = None
        self.write_kwargs = None

    def read_coils(self, **kwargs):
        self.read_kwargs = kwargs
        return _OkModbusResult()

    def write_coil(self, **kwargs):
        self.write_kwargs = kwargs
        return _OkModbusResult()


class _CapturingModbusAdcClient:
    def __init__(self):
        self.read_kwargs = None

    def read_input_registers(self, **kwargs):
        self.read_kwargs = kwargs
        return _OkModbusResult()


def test_piadc_health_rejects_mock_mode():
    plugin = PiadcPlugin(
        PluginConfig(
            plugin_id="piadc",
            enabled=True,
            connection_type="http",
            connection_params={"base_url": "http://localhost:8204"},
        )
    )
    plugin._client = _PiadcClient()

    health = asyncio.run(plugin.health_check())

    assert health.status == PluginStatus.ERROR
    assert health.compatible is False
    assert "mock_mode" in health.message


def test_piadc_health_includes_uninitialized_service_reason():
    plugin = PiadcPlugin(
        PluginConfig(
            plugin_id="piadc",
            enabled=True,
            connection_type="http",
            connection_params={"base_url": "http://localhost:8204"},
        )
    )
    plugin._client = _UninitializedPiadcClient()

    health = asyncio.run(plugin.health_check())
    result = asyncio.run(plugin.execute_command("read_sensor", {"sensor_id": "ai01"}))

    assert health.status == PluginStatus.ERROR
    assert health.compatible is False
    assert "invalid config register" in health.message
    assert result["success"] is False
    assert "invalid config register" in result["error"]


def test_piadc_health_points_non_rpi_hosts_to_remote_service(monkeypatch):
    monkeypatch.setenv("ADS1115_ALLOW_NON_RPI", "false")
    monkeypatch.setattr("oqlos.hardware.plugins.piadc._is_raspberry_pi_host", lambda: False)
    plugin = PiadcPlugin(
        PluginConfig(
            plugin_id="piadc",
            enabled=True,
            connection_type="http",
            connection_params={"base_url": "http://localhost:8204"},
        )
    )
    plugin._client = _FailingPiadcClient()

    health = asyncio.run(plugin.health_check())
    result = asyncio.run(plugin.execute_command("read_sensor", {"sensor_id": "ai01"}))

    assert health.status == PluginStatus.ERROR
    assert health.compatible is False
    assert "Raspberry Pi" in health.message
    assert "PIADC_URL" in health.message
    assert result["success"] is False
    assert "Raspberry Pi" in result["error"]


def test_lung_health_rejects_uninitialized_runtime():
    plugin = LungPlugin(
        PluginConfig(
            plugin_id="motor-tic249",
            enabled=True,
            connection_type="http",
            connection_params={"base_url": "http://localhost:8205"},
        )
    )
    plugin._client = _LungClient()

    health = asyncio.run(plugin.health_check())

    assert health.status == PluginStatus.ERROR
    assert health.compatible is False
    assert health.message == "Motor not initialized"


def test_modbus_rtu_health_timeout_does_not_block_event_loop():
    plugin = ModbusPlugin(
        PluginConfig(
            plugin_id="modbus-io",
            enabled=True,
            connection_type="modbus-rtu",
            connection_params={"serial_port": "/dev/ttyACM0"},
            timeout=0.1,
        )
    )
    plugin._client = _BlockingModbusClient()
    plugin._mode = "rtu"

    async def _run():
        started = time.monotonic()
        health = await plugin.health_check()
        return health, time.monotonic() - started

    health, elapsed = asyncio.run(_run())

    assert elapsed < 0.15
    assert health.status == PluginStatus.ERROR
    assert "timed out" in health.message


def test_modbus_adc_health_reads_input_registers():
    client = _CapturingModbusAdcClient()
    plugin = ModbusAdcPlugin(
        PluginConfig(
            plugin_id="modbus-adc",
            enabled=True,
            connection_type="modbus-rtu",
            connection_params={"serial_port": "/dev/ttyUSB0", "device_id": 1, "read_address": 0, "read_count": 8},
            timeout=0.5,
        )
    )
    plugin._client = client

    health = asyncio.run(plugin.health_check())

    assert health.status == PluginStatus.CONNECTED
    assert health.compatible is True
    assert health.details["registers"] == _OkModbusResult.registers
    assert client.read_kwargs == {"address": 0, "count": 8, "device_id": 1}


def test_modbus_adc_read_sensor_uses_channel_conversion():
    client = _CapturingModbusAdcClient()
    plugin = ModbusAdcPlugin(
        PluginConfig(
            plugin_id="modbus-adc",
            enabled=True,
            connection_type="modbus-rtu",
            connection_params={"serial_port": "/dev/ttyUSB0"},
            peripherals={
                "ai01": {
                    "name": "AI01",
                    "type": "sensor",
                    "scale": {"min": 0, "max": 5, "unit": "V"},
                    "conversion": {"type": "linear", "scale": 0.001, "offset": 0},
                },
            },
        )
    )
    plugin._client = client

    result = asyncio.run(plugin.execute_command("read_sensor", {"sensor_id": "ai01"}))

    assert result["success"] is True
    assert result["data"] == 0.101
    assert result["details"]["raw"] == 101
    assert result["details"]["unit"] == "V"


def test_modbus_rtu_uses_configured_device_id_for_health_and_writes():
    client = _CapturingModbusClient()
    plugin = ModbusPlugin(
        PluginConfig(
            plugin_id="modbus-io",
            enabled=True,
            connection_type="modbus-rtu",
            connection_params={"serial_port": "/dev/ttyACM0", "device_id": 7},
            timeout=0.1,
        )
    )
    plugin._client = client
    plugin._mode = "rtu"

    health = asyncio.run(plugin.health_check())
    result = asyncio.run(plugin.execute_command("set_coil", {"coil": 2, "value": True}))

    assert health.status == PluginStatus.CONNECTED
    assert health.details["device_id"] == 7
    assert client.read_kwargs["device_id"] == 7
    assert client.write_kwargs["device_id"] == 7
    assert result["success"] is True


def test_plugin_registry_health_checks_run_concurrently_with_timeout(monkeypatch):
    class SlowPlugin:
        async def health_check(self):
            await asyncio.sleep(1.0)

    class FastPlugin:
        async def health_check(self):
            from oqlos.hardware.plugins.base import PluginHealth

            return PluginHealth(
                status=PluginStatus.CONNECTED,
                message="fast ok",
                compatible=True,
            )

    old_instances = PluginRegistry._instances
    monkeypatch.setattr(
        PluginRegistry,
        "_instances",
        {"slow": SlowPlugin(), "fast": FastPlugin()},
    )

    try:
        results = asyncio.run(PluginRegistry.health_check_all(timeout=0.01))
    finally:
        monkeypatch.setattr(PluginRegistry, "_instances", old_instances)

    assert results["fast"].status == PluginStatus.CONNECTED
    assert results["slow"].status == PluginStatus.ERROR
    assert "timed out" in results["slow"].message
