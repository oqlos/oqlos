"""Tests for hardware identification diagnostics."""

from __future__ import annotations

import asyncio

import pytest

from oqlos.api import hardware as hw
from oqlos.api import hardware_identify as hw_identify
from oqlos.api import hardware_probe as hw_probe
from oqlos.api import hardware_runtime as hw_runtime
from oqlos.errors import OqlosError


from oqlos.api import hardware_peripherals_routes as hw_peripherals


def _patch_gateway(monkeypatch, gateway):
    monkeypatch.setattr(hw, "_gw", lambda: gateway)
    monkeypatch.setattr(hw_runtime, "get_hardware_gateway", lambda: gateway)
    monkeypatch.setattr(hw_identify, "get_hardware_gateway", lambda: gateway)
    monkeypatch.setattr(hw_peripherals, "get_hardware_gateway", lambda: gateway)


def _patch_probe(monkeypatch, name, value):
    monkeypatch.setattr(hw_probe, name, value)
    if hasattr(hw, name):
        monkeypatch.setattr(hw, name, value)


def _patch_platform(monkeypatch, name, value):
    from oqlos.api import hardware_platform as hw_platform

    monkeypatch.setattr(hw_platform, name, value)
    if hasattr(hw, name):
        monkeypatch.setattr(hw, name, value)


class _FakeGateway:
    async def health(self) -> dict[str, str]:
        return {
            "mode": "real",
            "modbus-adc": "ok",
            "motor": "ok",
            "modbus": "ok",
        }


class _UnavailableAdcGateway:
    async def health(self) -> dict[str, object]:
        return {
            "mode": "real",
            "modbus-adc": {
                "status": "error",
                "message": "Modbus ADC read_input_registers timed out after 2.0s",
                "compatible": False,
            },
        }

    async def read_sensor(self, sensor_id: str) -> float:
        raise AssertionError(f"unexpected live read for {sensor_id}")


def test_collect_hardware_diagnostics_exposes_ports(monkeypatch):
    _patch_probe(
        monkeypatch,
        "_scan_usb_devices",
        lambda: [
            {
                "vendor_id": "1a86",
                "product_id": "7523",
                "manufacturer": "QinHeng",
                "product": "USB Single Serial",
                "serial": "5958006895",
                "path": "/sys/bus/usb/devices/1-1",
            }
        ],
    )
    monkeypatch.setattr(
        hw_probe,
        "list_serial_ports",
        lambda: [
            {
                "device": "/dev/ttyUSB0",
                "manufacturer": "QinHeng",
                "product": "USB Single Serial",
                "serial_number": "5958006895",
                "vid": 6790,
                "pid": 29987,
            }
        ],
    )
    monkeypatch.setattr(
        hw_probe.glob,
        "glob",
        lambda pattern: ["/dev/i2c-0"] if pattern == "/dev/i2c-*" else [],
    )

    diagnostics = hw._collect_hardware_diagnostics()

    assert diagnostics["usb_devices"][0]["product_id"] == "7523"
    assert diagnostics["serial_ports"][0]["device"] == "/dev/ttyUSB0"
    assert diagnostics["i2c_buses"] == ["/dev/i2c-0"]


def test_platform_reports_modbus_adc_as_analog_input(monkeypatch):
    monkeypatch.setenv("OQLOS_ADC_SOURCE", "modbus-adc")
    monkeypatch.setenv("OQLOS_MODBUS_ADC_SERIAL_PORT", "/dev/modbus-adc")

    platform = hw._detect_runtime_platform()

    assert platform["analog_input_driver_role"] == "modbus-rtu"
    assert platform["modbus_adc_driver_role"] == "modbus-rtu"
    assert platform["modbus_adc_serial_port"] == "/dev/modbus-adc"
    assert platform["piadc_driver_role"] == "replaced-by-modbus-adc"


def test_platform_reports_usb_adc_stack_without_legacy_modbus_probe(monkeypatch):
    monkeypatch.setenv("OQLOS_ADC_SOURCE", "usb-adc-stack")

    platform = hw._detect_runtime_platform()

    assert platform["analog_input_driver_role"] == "usb-adc-stack"
    assert platform["modbus_adc_selected"] == "disabled"
    assert platform["modbus_adc_driver_role"] == "disabled"
    assert platform["modbus_adc_local_probe_allowed"] is False
    assert platform["piadc_driver_role"] == "replaced-by-usb-adc-stack"
    assert platform["analog_input_devices"] == [
        {
            "device_id": "usb-adc-mcp2221",
            "adapter": "usb-adc-mcp2221",
            "inputs": ["ai01"],
            "physical_inputs": ["MCP2221A.G1"],
        },
        {
            "device_id": "usb-adc-dfr1184",
            "adapter": "usb-adc-dfr1184",
            "inputs": ["ai02", "ai03"],
            "physical_inputs": ["DFR1184.AIN1", "DFR1184.AIN2"],
        },
    ]


def test_hardware_identify_includes_diagnostics(monkeypatch):
    _patch_gateway(monkeypatch, _FakeGateway())
    _patch_probe(
        monkeypatch,
        "_probe_selected_hardware",
        lambda _ids: {
            "motor-tic249": {"connected": False},
            "motor-dri0050": {"connected": True, "serial_port": "/dev/ttyUSB0"},
            "modbus-adc": {"connected": False},
            "modbus-io": {"connected": False},
        },
    )
    _patch_probe(
        monkeypatch,
        "_collect_hardware_diagnostics",
        lambda: {
            "usb_devices": [{"vendor_id": "1a86", "product_id": "7523"}],
            "serial_ports": [{"device": "/dev/ttyUSB0"}],
            "i2c_buses": ["/dev/i2c-0"],
        },
    )

    result = asyncio.run(hw.hardware_identify(scan="always"))

    assert result["mode"] == "real"
    statuses = {adapter["id"]: adapter["status"] for adapter in result["adapters"]}
    assert statuses["motor-dri0050"] == "ok"
    assert statuses["modbus-io"] in {"offline", "no-access", "adapter-only"}
    assert statuses["modbus-adc"] in {"offline", "no-access", "adapter-only"}
    assert result["detected"] == sum(
        1 for status in statuses.values() if status in {"ok", "adapter-only"}
    )
    assert result["total"] == len(result["adapters"])
    assert result["diagnostics"]["health"]["motor"] == "ok"
    assert result["diagnostics"]["serial_ports"][0]["device"] == "/dev/ttyUSB0"
    assert "platform" in result
    assert any(adapter["id"] == "motor-dri0050" for adapter in result["adapters"])


def test_hardware_identify_default_skips_live_probe(monkeypatch):
    _patch_gateway(monkeypatch, _FakeGateway())

    def _unexpected_live_probe(*_args):
        raise AssertionError("default identify must not run a live hardware scan")

    _patch_probe(monkeypatch, "_probe_selected_hardware", _unexpected_live_probe)
    _patch_probe(monkeypatch, "_collect_hardware_diagnostics", lambda: {})

    result = asyncio.run(hw.hardware_identify())

    assert result["diagnostics"]["scan_mode"] == "never"
    assert result["diagnostics"]["scan_performed"] is False


def test_hardware_identify_includes_usb_adc_component_health(monkeypatch):
    _patch_gateway(monkeypatch, _FakeGateway())
    monkeypatch.setattr(
        hw_identify.platform,
        "_detect_runtime_platform",
        lambda: {
            "analog_input_driver_role": "usb-adc-stack",
            "analog_input_devices": [],
        },
    )

    async def _health(_url, *, timeout_seconds):
        assert timeout_seconds > 0
        return {
            "ok": False,
            "components": {"usb-adc-dfr1184": {"ok": False}},
        }

    monkeypatch.setattr(hw_identify, "read_usb_adc_health", _health)

    result = asyncio.run(hw.hardware_identify())

    assert result["diagnostics"]["analog_input_health"]["ok"] is False


def test_read_sensors_batch_raises_typed_error_when_all_adc_transports_are_down(monkeypatch):
    _patch_gateway(monkeypatch, _UnavailableAdcGateway())

    with pytest.raises(OqlosError) as caught:
        asyncio.run(hw.read_sensors_batch(sensor_ids="ai01,ai02,ai03"))
    assert caught.value.status_code == 503
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "hw_usb_adc_sidecar_unreachable"
    assert "diagnostics" in caught.value.detail


def test_hardware_temperature_returns_compatible_payload(monkeypatch):
    monkeypatch.setattr(
        hw_runtime,
        "read_cpu_temperature",
        lambda: {"cpu_temp_celsius": None, "source": None, "available": False},
    )

    result = asyncio.run(hw.hardware_temperature())

    assert result["ok"] is False
    assert result["result"]["data"]["available"] is False
    assert result["peripheral_id"] == "cpu-temperature"


def test_hardware_diagnose_keeps_sensor_errors_in_payload(monkeypatch):
    _patch_gateway(monkeypatch, _UnavailableAdcGateway())

    result = asyncio.run(hw.hardware_diagnose())

    assert result["ok"] is True
    assert result["gateway_mode"] == "real"
    assert result["sensors"]["ai01"]["ok"] is False


def test_modbus_adc_raw_raises_typed_error_when_profile_is_unavailable(monkeypatch):
    _patch_gateway(monkeypatch, _UnavailableAdcGateway())

    with pytest.raises(OqlosError) as caught:
        asyncio.run(hw.read_modbus_adc_raw())
    assert caught.value.status_code == 503
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "modbus_adc_not_detected"
    assert caught.value.detail["modbus_adc_health"]["compatible"] is False


class _ModbusTimeoutGateway:
    async def health(self) -> dict[str, object]:
        return {
            "mode": "real",
            "modbus-adc": {"status": "connected", "compatible": True},
            "motor-tic249": {"status": "connected", "compatible": True},
            "motor-dri0050": {"status": "connected", "compatible": True},
            "modbus-io": {
                "status": "error",
                "message": "Modbus RTU read_coils timed out after 2.0s",
                "compatible": False,
            },
        }


def test_hardware_identify_reports_modbus_timeout_as_adapter_only(monkeypatch):
    _patch_gateway(monkeypatch, _ModbusTimeoutGateway())

    def _unexpected_live_probe(*_args):
        raise AssertionError(
            "modbus timeout should use plugin health, not a second serial probe"
        )

    _patch_probe(monkeypatch, "_probe_all_hardware", _unexpected_live_probe)
    _patch_probe(monkeypatch, "_collect_hardware_diagnostics", lambda: {})

    result = asyncio.run(hw.hardware_identify())
    modbus = next(
        adapter for adapter in result["adapters"] if adapter["id"] == "modbus-io"
    )

    assert modbus["status"] == "adapter-only"
    assert "did not answer" in modbus["probe"]["diagnosis"]
