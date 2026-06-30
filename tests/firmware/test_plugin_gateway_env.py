"""Tests for deployment environment overrides in the plugin hardware gateway."""

from __future__ import annotations

import asyncio

from oqlos.hardware.plugin_gateway import PluginHardwareGateway
from oqlos.hardware.plugins import PluginConfig, PluginHealth, PluginRegistry, PluginStatus


def test_plugin_gateway_env_overrides_service_urls(monkeypatch):
    gateway = PluginHardwareGateway(mode="mock")
    gateway._plugin_configs = {
        "piadc": PluginConfig(
            plugin_id="piadc",
            connection_params={"base_url": "http://localhost:8204"},
        ),
        "motor-dri0050": PluginConfig(
            plugin_id="motor-dri0050",
            connection_params={"base_url": "http://localhost:8203"},
        ),
        "motor-tic249": PluginConfig(
            plugin_id="motor-tic249",
            connection_params={"base_url": "http://localhost:8205"},
        ),
    }

    monkeypatch.setenv("OQLOS_PIADC_URL", "http://adc-controller.local:8204/")
    monkeypatch.setenv("OQLOS_MOTOR_URL", "http://pump-controller.local:8203")
    monkeypatch.setenv("OQLOS_LUNG_MOTOR_URL", "http://lung-controller.local:8205")

    gateway._apply_env_overrides()

    assert gateway._plugin_configs["piadc"].connection_params["base_url"] == "http://adc-controller.local:8204"
    assert gateway._plugin_configs["motor-dri0050"].connection_params["base_url"] == "http://pump-controller.local:8203"
    assert gateway._plugin_configs["motor-tic249"].connection_params["base_url"] == "http://lung-controller.local:8205"


def test_plugin_gateway_env_overrides_modbus_params(monkeypatch):
    gateway = PluginHardwareGateway(mode="mock")
    gateway._plugin_configs = {
        "modbus-io": PluginConfig(
            plugin_id="modbus-io",
            connection_type="modbus-rtu",
            connection_params={
                "serial_port": "/dev/ttyACM1",
                "baudrate": 19200,
                "parity": "N",
                "device_id": 1,
            },
        ),
    }

    monkeypatch.setenv("OQLOS_MODBUS_SERIAL_PORT", "/dev/serial/by-id/test-modbus")
    monkeypatch.setenv("OQLOS_MODBUS_BAUD", "9600")
    monkeypatch.setenv("OQLOS_MODBUS_PARITY", "E")
    monkeypatch.setenv("OQLOS_MODBUS_DEVICE_ID", "7")

    gateway._apply_env_overrides()

    assert gateway._plugin_configs["modbus-io"].connection_params == {
        "serial_port": "/dev/serial/by-id/test-modbus",
        "baudrate": 9600,
        "parity": "E",
        "device_id": 7,
    }


def test_plugin_gateway_env_overrides_modbus_adc_params(monkeypatch):
    gateway = PluginHardwareGateway(mode="mock")
    gateway._plugin_configs = {
        "modbus-adc": PluginConfig(
            plugin_id="modbus-adc",
            connection_type="modbus-rtu",
            connection_params={
                "serial_port": "/dev/ttyUSB0",
                "baudrate": 9600,
                "parity": "N",
                "device_id": 1,
                "read_address": 0,
                "read_count": 8,
            },
        ),
    }

    monkeypatch.setenv("OQLOS_MODBUS_ADC_SERIAL_PORT", "/dev/serial/by-id/test-adc")
    monkeypatch.setenv("OQLOS_MODBUS_ADC_BAUD", "19200")
    monkeypatch.setenv("OQLOS_MODBUS_ADC_PARITY", "E")
    monkeypatch.setenv("OQLOS_MODBUS_ADC_DEVICE_ID", "3")
    monkeypatch.setenv("OQLOS_MODBUS_ADC_READ_ADDRESS", "2")
    monkeypatch.setenv("OQLOS_MODBUS_ADC_READ_COUNT", "4")

    gateway._apply_env_overrides()

    assert gateway._plugin_configs["modbus-adc"].connection_params == {
        "serial_port": "/dev/serial/by-id/test-adc",
        "baudrate": 19200,
        "parity": "E",
        "device_id": 3,
        "read_address": 2,
        "read_count": 4,
    }


def test_set_pump_uses_registry_instance_that_recovers_after_startup(monkeypatch):
    class RecoveredMotorPlugin:
        async def health_check(self):
            return PluginHealth(
                status=PluginStatus.CONNECTED,
                message="Motor is healthy",
                compatible=True,
            )

        async def execute_command(self, command, params):
            return {"success": True, "command": command, "data": params}

    plugin = RecoveredMotorPlugin()
    gateway = PluginHardwareGateway(mode="mock")
    gateway.mode = "real"
    gateway._init_done = True
    gateway._plugin_configs = {
        "motor-dri0050": PluginConfig(
            plugin_id="motor-dri0050",
            connection_params={"base_url": "http://motor:8203"},
        )
    }

    monkeypatch.setattr(
        PluginRegistry,
        "get_instance",
        classmethod(lambda cls, plugin_id: plugin if plugin_id == "motor-dri0050" else None),
    )

    result = asyncio.run(gateway.set_pump(20))

    assert result == {"success": True, "command": "set_speed", "data": {"power_pct": 20}}
    assert gateway._plugins["motor-dri0050"] is plugin


def test_plugin_gateway_disable_plugins_env(monkeypatch):
    gateway = PluginHardwareGateway(mode="mock")
    gateway._plugin_configs = {
        "modbus-io": PluginConfig(plugin_id="modbus-io", enabled=True),
        "motor-dri0050": PluginConfig(plugin_id="motor-dri0050", enabled=True),
        "motor-tic249": PluginConfig(plugin_id="motor-tic249", enabled=True),
    }

    monkeypatch.setenv("OQLOS_DISABLE_PLUGINS", "motor-dri0050,motor-tic249")

    gateway._apply_env_overrides()

    assert gateway._plugin_configs["modbus-io"].enabled is True
    assert gateway._plugin_configs["motor-dri0050"].enabled is False
    assert gateway._plugin_configs["motor-tic249"].enabled is False


def test_plugin_gateway_allow_list_plugins_env(monkeypatch):
    gateway = PluginHardwareGateway(mode="mock")
    gateway._plugin_configs = {
        "modbus-io": PluginConfig(plugin_id="modbus-io", enabled=True),
        "modbus-adc": PluginConfig(plugin_id="modbus-adc", enabled=True),
        "motor-dri0050": PluginConfig(plugin_id="motor-dri0050", enabled=True),
    }

    monkeypatch.setenv("OQLOS_HARDWARE_PLUGINS", "modbus-io,modbus-adc")

    gateway._apply_env_overrides()

    assert gateway._plugin_configs["modbus-io"].enabled is True
    assert gateway._plugin_configs["modbus-adc"].enabled is True
    assert gateway._plugin_configs["motor-dri0050"].enabled is False


def test_health_reports_configured_disabled_plugins(monkeypatch):
    async def _empty_health_result(cls, plugin_id, timeout=None):
        return None

    gateway = PluginHardwareGateway(mode="mock")
    gateway.mode = "real"
    gateway._init_done = True
    gateway._plugin_configs = {
        "modbus-adc": PluginConfig(
            plugin_id="modbus-adc",
            enabled=False,
            connection_type="modbus-rtu",
            connection_params={"serial_port": "/dev/serial/by-id/adc-not-present"},
        ),
    }

    monkeypatch.setattr(
        PluginRegistry,
        "health_check",
        classmethod(_empty_health_result),
    )

    result = asyncio.run(gateway.health())

    assert result["modbus-adc"] == {
        "status": "disabled",
        "message": "Plugin is disabled in OqlOS configuration",
        "compatible": False,
    }


def test_health_does_not_poll_configured_disabled_plugins(monkeypatch):
    calls: list[str] = []

    async def _health_result(cls, plugin_id, timeout=None):
        calls.append(plugin_id)
        return PluginHealth(
            status=PluginStatus.CONNECTED,
            message=f"{plugin_id} healthy",
            compatible=True,
        )

    gateway = PluginHardwareGateway(mode="mock")
    gateway.mode = "real"
    gateway._init_done = True
    gateway._plugin_configs = {
        "modbus-io": PluginConfig(plugin_id="modbus-io", enabled=True),
        "modbus-adc": PluginConfig(plugin_id="modbus-adc", enabled=False),
    }

    monkeypatch.setattr(
        PluginRegistry,
        "health_check",
        classmethod(_health_result),
    )

    result = asyncio.run(gateway.health())

    assert calls == ["modbus-io"]
    assert result["modbus-io"] == {
        "status": "connected",
        "message": "modbus-io healthy",
        "compatible": True,
    }
    assert result["modbus-adc"] == {
        "status": "disabled",
        "message": "Plugin is disabled in OqlOS configuration",
        "compatible": False,
    }
