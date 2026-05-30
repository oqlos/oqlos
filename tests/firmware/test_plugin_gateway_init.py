"""Tests for deterministic hardware plugin initialization."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from oqlos.hardware.plugin_gateway import PluginHardwareGateway
from oqlos.hardware.plugins import PluginConfig, PluginHealth, PluginStatus


def test_health_awaits_ensure_initialized_before_checks(monkeypatch) -> None:
    gateway = PluginHardwareGateway(mode="mock")
    gateway.mode = "real"
    gateway._init_done = True
    calls: list[str] = []

    async def _track_ensure() -> None:
        calls.append("ensure")

    async def _fake_health_all(*, timeout=None):
        calls.append("health_all")
        return {}

    monkeypatch.setattr(gateway, "ensure_initialized", _track_ensure)
    monkeypatch.setattr(
        "oqlos.hardware.plugins.registry.PluginRegistry.health_check_all",
        AsyncMock(side_effect=_fake_health_all),
    )
    gateway._plugin_configs = {}

    asyncio.run(gateway.health())

    assert calls == ["ensure", "health_all"]


def test_initialize_plugins_records_summary(monkeypatch) -> None:
    gateway = PluginHardwareGateway(mode="mock")
    gateway.mode = "real"
    gateway._init_done = False
    gateway._plugin_configs = {
        "modbus-io": PluginConfig(
            plugin_id="modbus-io",
            enabled=True,
            connection_type="modbus-rtu",
            connection_params={"serial_port": "/dev/ttyTEST", "baudrate": 9600, "device_id": 2},
        ),
    }

    class _FakeModbus:
        async def connect(self) -> bool:
            return True

    async def _fake_create(plugin_id: str, config: PluginConfig):
        return _FakeModbus()

    monkeypatch.setattr(
        "oqlos.hardware.plugins.registry.PluginRegistry.create_instance",
        _fake_create,
    )

    asyncio.run(gateway._initialize_plugins())

    assert gateway._init_done is True
    assert "modbus-io" in gateway.last_init_summary.get("connected", [])
    assert gateway._plugins.get("modbus-io") is not None
