"""Regression tests for hardware diagnostic-command error boundary."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oqlos.api import _hw3_peripheral as peripheral
from oqlos.api._hw3_models import DiagnosticCommandRequest
from oqlos.errors import OqlosError
from oqlos.errors.fastapi_integration import install_oqlos_error_handler


def test_peripheral_status_rejects_ok_false_for_dri0050(monkeypatch):
    async def _unavailable(_peripheral_id, _command, _args):
        return {
            "ok": False,
            "peripheral_id": "motor-dri0050",
            "error": "DRI0050 sidecar down",
        }

    monkeypatch.setattr(peripheral, "_run_diagnostic", _unavailable)

    with pytest.raises(OqlosError) as caught:
        asyncio.run(peripheral.hardware_peripheral_status_v3("motor-dri0050"))

    assert caught.value.status_code == 503
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "hw_dri0050_sidecar_unreachable"
    assert caught.value.detail["peripheral_id"] == "motor-dri0050"


def test_peripheral_status_rejects_ok_false_for_tic249(monkeypatch):
    async def _unavailable(_peripheral_id, _command, _args):
        return {
            "ok": False,
            "peripheral_id": "motor-tic249",
            "error": "Tic249 sidecar down",
        }

    monkeypatch.setattr(peripheral, "_run_diagnostic", _unavailable)

    with pytest.raises(OqlosError) as caught:
        asyncio.run(peripheral.hardware_peripheral_status_v3("motor-tic249"))

    assert caught.value.status_code == 503
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "hw_tic249_sidecar_unreachable"


def test_unknown_peripheral_status_uses_typed_configuration_error(monkeypatch):
    async def _boom(_peripheral_id, _command, _args):
        raise RuntimeError("No active instance")

    async def _identify(*, scan):
        assert scan == "never"
        return {"adapters": []}

    from oqlos.api import hardware as hw

    monkeypatch.setattr(peripheral, "_run_diagnostic", _boom)
    monkeypatch.setattr(hw, "hardware_identify", _identify)

    with pytest.raises(OqlosError) as caught:
        asyncio.run(peripheral.hardware_peripheral_status_v3("not-a-device"))

    assert caught.value.status_code == 503
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "config_unavailable"


def test_peripheral_status_keeps_successful_read_as_http_payload(monkeypatch):
    async def _healthy(_peripheral_id, _command, _args):
        return {"ok": True, "peripheral_id": "motor-dri0050", "power_pct": 0}

    monkeypatch.setattr(peripheral, "_run_diagnostic", _healthy)

    result = asyncio.run(peripheral.hardware_peripheral_status_v3("motor-dri0050"))

    assert result == {"ok": True, "peripheral_id": "motor-dri0050", "power_pct": 0}


def test_artificial_lung_status_rejects_unsuccessful_manage_result(monkeypatch):
    from oqlos.hardware.transport import manage_ops

    async def _unavailable(_verb):
        return {"ok": False, "error": "Tic249 sidecar down"}

    monkeypatch.setattr(manage_ops, "run_manage_verb", _unavailable)

    with pytest.raises(OqlosError) as caught:
        asyncio.run(peripheral.hardware_peripheral_status_v3("artificial-lung"))

    assert caught.value.status_code == 503
    assert caught.value.issue_code == "hw_tic249_sidecar_unreachable"


def test_barcode_status_rejects_missing_adapter(monkeypatch):
    from oqlos.api import hardware as hw

    async def _identify(*, scan):
        assert scan == "never"
        return {"adapters": []}

    monkeypatch.setattr(hw, "hardware_identify", _identify)

    with pytest.raises(OqlosError) as caught:
        asyncio.run(peripheral.hardware_peripheral_status_v3("barcode-scanner"))

    assert caught.value.status_code == 503
    assert caught.value.issue_code == "config_unavailable"


def test_peripheral_status_http_failure_is_canonical_problem_details(monkeypatch):
    async def _unavailable(_peripheral_id, _command, _args):
        return {
            "ok": False,
            "peripheral_id": "motor-dri0050",
            "error": "DRI0050 sidecar down",
        }

    monkeypatch.setattr(peripheral, "_run_diagnostic", _unavailable)
    app = FastAPI()
    install_oqlos_error_handler(app)
    app.include_router(peripheral.sub_router, prefix="/api/v3/hardware")

    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/v3/hardware/peripheral-status/motor-dri0050",
        headers={"X-Correlation-ID": "cor-peripheral-status-test"},
    )

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["x-correlation-id"] == "cor-peripheral-status-test"
    body = response.json()
    assert body["ok"] is False
    assert body["code"] == body["error_code"] == "C2004-HW-0012"
    assert body["correlation_id"] == "cor-peripheral-status-test"
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "hw_dri0050_sidecar_unreachable"
    )
    assert body["metadata"]["context"]["peripheral_id"] == "motor-dri0050"


def test_diagnostic_command_raises_typed_tic249_error(monkeypatch):
    published: list[dict] = []

    async def _boom(_peripheral_id, _command, _args):
        raise RuntimeError("sidecar down")

    async def _publish(command, result, context=None):
        published.append({"command": command, "result": result, "context": context})

    monkeypatch.setattr(peripheral, "_run_diagnostic", _boom)
    monkeypatch.setattr(peripheral, "publish_hardware_command_event", _publish)

    with pytest.raises(OqlosError) as caught:
        asyncio.run(
            peripheral.hardware_diagnostic_command_v3(
                DiagnosticCommandRequest(
                    peripheral_id="tic249",
                    command="status",
                    args={},
                )
            )
        )
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "hw_tic249_sidecar_unreachable"
    assert published and published[0]["result"]["ok"] is False


def test_diagnostic_command_rejects_returned_ok_false(monkeypatch):
    async def _refused(_peripheral_id, _command, _args):
        return {
            "ok": False,
            "peripheral_id": "modbus-io",
            "command": "status",
            "error": "No Modbus response",
        }

    monkeypatch.setattr(peripheral, "_run_diagnostic", _refused)

    with pytest.raises(OqlosError) as caught:
        asyncio.run(
            peripheral.hardware_diagnostic_command_v3(
                DiagnosticCommandRequest(
                    peripheral_id="modbus-io", command="status", args={}
                )
            )
        )

    assert caught.value.status_code == 503
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "hw_modbus_no_response"


def test_diagnostic_command_http_failure_is_safe_problem_details(monkeypatch):
    async def _refused(_peripheral_id, _command, _args):
        return {
            "ok": False,
            "error": "password=hunter2 must not escape",
        }

    monkeypatch.setattr(peripheral, "_run_diagnostic", _refused)
    app = FastAPI()
    install_oqlos_error_handler(app)
    app.include_router(peripheral.sub_router, prefix="/api/v3/hardware")

    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/v3/hardware/diagnostic-command",
        json={"peripheral_id": "modbus-io", "command": "status", "args": {}},
        headers={"X-Correlation-ID": "cor-diagnostic-contract"},
    )

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "C2004-HW-0012"
    assert body["correlation_id"] == "cor-diagnostic-contract"
    assert body["component"] == "hardware-diagnostics"
    assert body["stage"] == "diagnostic.execute"
    assert body["metadata"]["context"]["problem_source"] == "upstream"
    assert body["metadata"]["context"]["upstream_target"] == (
        "hardware-peripheral://modbus-io"
    )
    assert "hunter2" not in response.text
    assert "traceback" not in response.text.lower()


def test_diagnostic_command_invalid_request_uses_data_code(monkeypatch):
    async def _invalid(_peripheral_id, _command, _args):
        raise ValueError("Unsupported diagnostic command 'spin' for peripheral 'rtc'")

    async def _publish(*_args, **_kwargs):
        return None

    monkeypatch.setattr(peripheral, "_run_diagnostic", _invalid)
    monkeypatch.setattr(peripheral, "publish_hardware_command_event", _publish)

    with pytest.raises(OqlosError) as caught:
        asyncio.run(
            peripheral.hardware_diagnostic_command_v3(
                DiagnosticCommandRequest(
                    peripheral_id="rtc", command="spin", args={}
                )
            )
        )

    assert caught.value.status_code == 400
    assert caught.value.public_code == "C2004-DATA-0002"
    assert caught.value.issue_code == "api_diagnostic_command_invalid"
