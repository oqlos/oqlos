"""Regression: v3 system routes for Modbus, RTC, and motor-scoped diagnosis."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oqlos.api import _hw3_system as system_hw
from oqlos.api import hardware_modbus_routes as modbus_hw
from oqlos.api._hw3_system import sub_router
from oqlos.errors.fastapi_integration import install_oqlos_error_handler


def test_hw3_system_router_includes_ui_module_routes() -> None:
    paths = {route.path for route in sub_router.routes}
    assert "/modbus/profile-channels" in paths
    assert "/modbus/channel-value" in paths
    assert "/modbus/coil-test/plan" in paths
    assert "/modbus/coil-test/pulse" in paths
    assert "/modbus/coil-test/stop" in paths
    assert "/rtc/status" in paths
    assert "/rtc/command" in paths
    assert "/diagnosis" in paths
    assert "/diagnosis/repair" in paths


def _client() -> TestClient:
    app = FastAPI()
    install_oqlos_error_handler(app)
    app.include_router(sub_router, prefix="/api/v3/hardware")
    return TestClient(app, raise_server_exceptions=False)


def test_modbus_autoconfigure_limits_safe_recovery_to_modbus(monkeypatch) -> None:
    calls = []

    async def _recover(name, **kwargs):
        calls.append((name, kwargs))
        return {"ok": True}

    monkeypatch.setattr(system_hw, "_hardware_v1_call", _recover)

    response = _client().post("/api/v3/hardware/modbus/autoconfigure")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert calls == [
        ("hardware_recover_route", {"scope": "safe", "devices": "modbus"})
    ]


def test_program_isolated_rejects_invalid_integer_before_hardware(monkeypatch) -> None:
    async def _unexpected_program(**_kwargs):
        raise AssertionError("invalid request must not reach Modbus programming")

    monkeypatch.setattr(modbus_hw, "hardware_modbus_wizard_program_isolated", _unexpected_program)

    response = _client().post(
        "/api/v3/hardware/modbus/wizard/program-isolated",
        json={"current_device_id": "not-an-integer"},
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "C2004-DATA-0002"
    assert body["metadata"]["diagnostics"]["issue_code"] == "api_modbus_wizard_invalid_request"
    assert body["metadata"]["context"]["field"] == "current_device_id"


def test_program_isolated_rejects_string_confirmation_before_hardware(monkeypatch) -> None:
    async def _unexpected_program(**_kwargs):
        raise AssertionError("ambiguous confirmation must not reach Modbus programming")

    monkeypatch.setattr(modbus_hw, "hardware_modbus_wizard_program_isolated", _unexpected_program)

    response = _client().post(
        "/api/v3/hardware/modbus/wizard/program-isolated",
        json={"confirm_isolated": "false"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "C2004-DATA-0002"
    assert body["metadata"]["context"]["field"] == "confirm_isolated"


def test_hui_al_rejects_unknown_command_with_typed_data_error() -> None:
    response = _client().post(
        "/api/v3/hardware/hui/al/password=hunter2",
        headers={"X-Correlation-ID": "cor-hui-command"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "C2004-DATA-0002"
    assert body["correlation_id"] == "cor-hui-command"
    assert body["component"] == "hardware-hui"
    assert body["stage"] == "command.validate"
    assert "hunter2" not in response.text


def test_systemd_control_rejects_unknown_action_with_typed_data_error() -> None:
    response = _client().post(
        "/api/v3/hardware/systemd/services/oqlos-hardware-api.service/destroy",
        headers={"X-Correlation-ID": "cor-systemd-action"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "C2004-DATA-0002"
    assert body["correlation_id"] == "cor-systemd-action"
    assert body["component"] == "systemd-control"
    assert body["stage"] == "action.validate"


@pytest.mark.parametrize(
    ("method", "path", "operation_id"),
    [
        (
            "POST",
            "/api/v3/hardware/systemd/services/password=hunter2.service/restart",
            "systemd.service.control",
        ),
        (
            "GET",
            "/api/v3/hardware/systemd/services/password=hunter2.service/logs",
            "systemd.service.logs",
        ),
    ],
)
def test_systemd_routes_reject_non_whitelisted_unit_with_typed_auth_error(
    monkeypatch, method: str, path: str, operation_id: str
) -> None:
    monkeypatch.setattr(
        "oqlos.hardware.systemd_services.is_whitelisted", lambda _unit: False
    )

    response = _client().request(
        method,
        path,
        headers={"X-Correlation-ID": "cor-systemd-unit"},
    )

    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "C2004-AUTH-0002"
    assert body["correlation_id"] == "cor-systemd-unit"
    assert body["component"] == "systemd-control"
    assert body["stage"] == "unit.authorize"
    assert body["metadata"]["diagnostics"]["issue_code"] == "api_systemd_unit_forbidden"
    assert body["metadata"]["context"]["operation_id"] == operation_id
    assert "hunter2" not in response.text


def test_systemd_control_failure_is_not_returned_as_http_200(monkeypatch) -> None:
    monkeypatch.setattr(
        "oqlos.hardware.systemd_services.control_service",
        lambda unit, action: {
            "ok": False,
            "unit": unit,
            "action": action,
            "error": "password=hunter2",
        },
    )

    response = _client().post(
        "/api/v3/hardware/systemd/services/oqlos-hardware-api.service/restart",
        headers={"X-Correlation-ID": "cor-systemd-failure"},
    )

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "C2004-HW-0012"
    assert body["correlation_id"] == "cor-systemd-failure"
    assert body["component"] == "systemd-control"
    assert body["stage"] == "action.execute"
    assert "hunter2" not in response.text
