"""Regression: v3 system routes for Modbus, RTC, and motor-scoped diagnosis."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

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
