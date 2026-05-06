"""Tests for deployment environment overrides in the plugin hardware gateway."""

from __future__ import annotations

from oqlos.hardware.plugin_gateway import PluginHardwareGateway
from oqlos.hardware.plugins import PluginConfig


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
