"""Regression tests for the legacy firmware adapter failure boundary."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import httpx
import pytest

from oqlos.hardware import firmware_adapter as adapter_module
from oqlos.hardware.firmware_adapter import FirmwareAdapter


class _Response:
    def __init__(self, payload: object):
        self.payload = payload
        self.status_code = 200

    def json(self) -> object:
        return self.payload

    def raise_for_status(self) -> None:
        return None


def _adapter(client: object) -> FirmwareAdapter:
    adapter = FirmwareAdapter.__new__(FirmwareAdapter)
    adapter.base_url = "http://localhost:8202"
    adapter.timeout = 5.0
    adapter.mock = False
    adapter.lung_motor_url = "http://localhost:8205"
    adapter._client = client
    return adapter


def test_is_available_treats_transport_failure_as_unavailable() -> None:
    request = httpx.Request("GET", "http://localhost:8202/api/v1/health")

    class Client:
        def get(self, _path: str) -> None:
            raise httpx.ConnectError("private-host failed", request=request)

    assert _adapter(Client()).is_available() is False


def test_is_available_does_not_mask_programming_defect() -> None:
    class Client:
        def get(self, _path: str) -> None:
            raise AttributeError("programming defect")

    with pytest.raises(AttributeError, match="programming defect"):
        _adapter(Client()).is_available()


def test_read_sensor_falls_back_to_state_after_transport_failure() -> None:
    request = httpx.Request(
        "GET", "http://localhost:8202/api/v1/hardware/sensor/nc-sensor"
    )

    class Client:
        def get(self, path: str) -> _Response:
            if path.startswith("/api/v1/hardware/sensor/"):
                raise httpx.ConnectError("sensor offline", request=request)
            return _Response({"peripherals": {"nc-sensor": {"currentValue": "12.5"}}})

    assert _adapter(Client()).read_sensor("AI01") == 12.5


def test_read_sensor_does_not_mask_programming_defect() -> None:
    class Client:
        def get(self, _path: str) -> None:
            raise AttributeError("broken client")

    with pytest.raises(AttributeError, match="broken client"):
        _adapter(Client()).read_sensor("AI01")


def test_read_all_sensors_degrades_only_expected_payload_failures() -> None:
    class Client:
        def get(self, _path: str) -> _Response:
            return _Response({"value": "not-a-number"})

    assert set(_adapter(Client()).read_all_sensors().values()) == {0.0}


def test_dispatch_returns_catalogued_sanitized_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "token=do-not-publish /private/device/path"
    request = httpx.Request("POST", "http://localhost:8202/api/v1/hardware/pump")
    adapter = _adapter(SimpleNamespace())

    def fail_set_peripheral(_target: str, _value: object) -> dict:
        raise httpx.ConnectError(secret, request=request)

    adapter.set_peripheral = fail_set_peripheral  # type: ignore[method-assign]
    with caplog.at_level(logging.WARNING, logger=adapter_module.__name__):
        result = adapter.dispatch_action("Pump", "set", "5")

    assert result == {
        "ok": False,
        "detail": "Required hardware is unavailable",
        "data": {},
        "status": 503,
        "error_code": "C2004-HW-0012",
        "issue_code": "firmware-command-unavailable",
        "architecture": "SOA",
        "layer": "firmware",
        "component": "firmware-adapter",
        "stage": "command.execute",
        "problem_source": "hardware-runtime://firmware-adapter",
        "operation_id": "firmware.command.dispatch",
        "owner": "owner://domain/hardware",
        "retryable": False,
    }
    assert secret not in caplog.text
    assert "ConnectError" in caplog.text


def test_dispatch_rejects_non_object_firmware_payload_without_leaking_it() -> None:
    class Client:
        def post(
            self, _path: str, params: object = None, json: object = None
        ) -> _Response:
            return _Response(["private", "payload"])

    result = _adapter(Client()).dispatch_action("Pump", "set", "5")

    assert result["ok"] is False
    assert result["error_code"] == "C2004-HW-0012"
    assert "private" not in str(result)


def test_dispatch_does_not_mask_programming_defect() -> None:
    adapter = _adapter(SimpleNamespace())

    def fail_set_peripheral(_target: str, _value: object) -> dict:
        raise AttributeError("programming defect")

    adapter.set_peripheral = fail_set_peripheral  # type: ignore[method-assign]

    with pytest.raises(AttributeError, match="programming defect"):
        adapter.dispatch_action("Pump", "set", "5")


def test_lung_url_configuration_failure_is_not_silently_replaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _adapter(SimpleNamespace())
    adapter.lung_motor_url = ""

    def fail_settings() -> None:
        raise AttributeError("invalid settings object")

    monkeypatch.setattr(adapter_module, "get_settings", fail_settings)

    with pytest.raises(AttributeError, match="invalid settings object"):
        adapter._get_lung_motor_url()
