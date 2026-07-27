"""Tests for Modbus baud settings and init probe sequence."""

from __future__ import annotations

from types import SimpleNamespace

import importlib.util
from pathlib import Path

import pytest

_SETTINGS_PATH = Path(__file__).resolve().parents[2] / "oqlos" / "api" / "hardware_modbus_settings.py"
_spec = importlib.util.spec_from_file_location("hardware_modbus_settings", _SETTINGS_PATH)
settings = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(settings)


@pytest.fixture(autouse=True)
def _clear_user_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("OQLOS_STATE_DIR", str(tmp_path))
    settings.clear_modbus_baud_user_settings_cache()
    monkeypatch.setattr(
        settings,
        "_runtime_serial_ports",
        lambda: {
            "io_serial_port": "/dev/ttyUSB0",
            "adc_serial_port": "/dev/ttyUSB1",
            "shared_serial_port": "",
            "topology": "separate-adapters",
        },
    )
    monkeypatch.setattr(
        settings,
        "_topology_module",
        lambda: SimpleNamespace(_modbus_io_device_ids=lambda: [1]),
    )
    yield
    settings.clear_modbus_baud_user_settings_cache()


def test_build_init_baud_sequence_starts_at_baseline():
    assert settings.build_init_baud_sequence(4800) == [4800]
    assert settings.build_init_baud_sequence(115200) == [4800, 115200]
    assert settings.build_init_baud_sequence(9600) == [4800, 9600]


def test_normalize_target_baud_accepts_4800_through_115200():
    assert settings.normalize_target_baud(4800) == 4800
    assert settings.normalize_target_baud(9600) == 9600
    assert settings.normalize_target_baud(115200) == 115200
    assert settings.normalize_target_baud(2400, default=4800) == 4800


def test_normalize_probe_baudrates_keeps_baseline_first():
    assert settings.normalize_probe_baudrates([115200, 9600], 115200) == [4800, 115200, 9600]


def test_write_and_read_modbus_baud_settings(tmp_path):
    cfg = SimpleNamespace(modbus_baud=4800, modbus_adc_baud=9600, modbus_parity="N", modbus_adc_device_id=2)
    saved = settings.write_modbus_baud_settings(
        cfg,
        {"target_baudrate": 57600, "profile_id": "modbus-io", "active_profile": "modbus-io"},
    )
    assert saved["target_baudrate"] == 57600
    assert saved["baud_probe_sequence"] == [4800, 57600]
    assert saved["profiles"]["modbus-io"]["target_baudrate"] == 57600

    loaded = settings.read_modbus_baud_settings(cfg)
    assert loaded["target_baudrate"] == 57600
    assert (tmp_path / "modbus-user-settings.json").exists()


def test_profiles_are_independent(tmp_path):
    cfg = SimpleNamespace(
        modbus_baud=4800,
        modbus_adc_baud=9600,
        modbus_parity="N",
        modbus_device_id=1,
        modbus_adc_device_id=2,
        modbus_serial_port="/dev/ttyUSB0",
        modbus_adc_serial_port="/dev/ttyUSB1",
    )
    settings.write_modbus_baud_settings(
        cfg,
        {"profile_id": "modbus-adc", "active_profile": "modbus-adc", "target_baudrate": 115200},
    )
    settings.write_modbus_baud_settings(cfg, {"profile_id": "modbus-io", "target_baudrate": 38400})

    loaded = settings.read_modbus_baud_settings(cfg)
    assert loaded["profiles"]["modbus-adc"]["target_baudrate"] == 115200
    assert loaded["profiles"]["modbus-io"]["target_baudrate"] == 38400
    assert loaded["active_profile"] == "modbus-adc"
    assert settings.effective_modbus_target_baud(cfg) == 115200


def test_runtime_plugin_overrides_use_persisted_io_profile(monkeypatch):
    cfg = SimpleNamespace(
        modbus_baud=4800,
        modbus_adc_baud=9600,
        modbus_parity="N",
        modbus_adc_parity="E",
        modbus_device_id=2,
        modbus_adc_device_id=1,
        modbus_serial_port="/dev/ttyUSB0",
        modbus_adc_serial_port="/dev/ttyUSB1",
    )
    monkeypatch.setattr(settings, "_profile_device_ids", lambda pid, _cfg: [2] if pid == "modbus-io" else [1])
    settings.write_modbus_baud_settings(
        cfg,
        {
            "profile_id": "modbus-io",
            "active_profile": "modbus-io",
            "target_baudrate": 4800,
            "target_parity": "N",
        },
    )
    plugin = SimpleNamespace(
        connection_type="modbus-rtu",
        connection_params={"serial_port": "/dev/ttyACM0", "baudrate": 9600, "device_id": 1},
    )

    applied = settings.apply_modbus_runtime_settings(cfg, {"modbus-io": plugin})

    assert applied["modbus-io"]["baudrate"] == 4800
    assert applied["modbus-io"]["device_id"] == 2
    assert plugin.connection_params["serial_port"] == "/dev/ttyUSB0"
    assert plugin.connection_params["baudrate"] == 4800
