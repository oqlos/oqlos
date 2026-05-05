"""Tests for hardware plugin health semantics."""

from __future__ import annotations

import asyncio
import time

from oqlos.hardware.plugins.base import PluginConfig, PluginStatus
from oqlos.hardware.plugins.lung import LungPlugin
from oqlos.hardware.plugins.modbus import ModbusPlugin
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
