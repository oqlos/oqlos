"""Regression: platform detection must degrade gracefully without pimodbus installed."""

from __future__ import annotations

from oqlos.api import hardware_platform


def test_detect_runtime_platform_survives_missing_pimodbus(monkeypatch) -> None:
    def _boom():
        raise RuntimeError("Modbus discovery needs the 'pimodbus' package, which is not installed.")

    monkeypatch.setattr(hardware_platform, "list_serial_ports", _boom)

    payload = hardware_platform._detect_runtime_platform()

    assert payload["serial_ports"] == []
    assert "pimodbus" in payload["serial_ports_error"]


def test_detect_runtime_platform_omits_error_key_on_success(monkeypatch) -> None:
    monkeypatch.setattr(
        hardware_platform,
        "list_serial_ports",
        lambda: [{"device": "/dev/ttyUSB0"}, {"device": "/dev/ttyACM0"}],
    )

    payload = hardware_platform._detect_runtime_platform()

    assert payload["serial_ports"] == ["/dev/ttyUSB0", "/dev/ttyACM0"]
    assert "serial_ports_error" not in payload
