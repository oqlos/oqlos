"""Regression tests for extracted Modbus HTTP routes."""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oqlos.api import hardware_modbus_routes as modbus_hw
from oqlos.errors import OqlosError
from oqlos.errors.fastapi_integration import install_oqlos_error_handler


def test_hardware_modbus_router_includes_channel_and_wizard_paths():
    paths = {route.path for route in modbus_hw.router.routes}
    assert "/modbus/waveshare-diagnose" in paths
    assert "/modbus/wizard/plan" in paths
    assert "/modbus/wizard/probe-isolated" in paths
    assert "/modbus/wizard/program-isolated" in paths
    assert "/modbus/profile-channels" in paths
    assert "/modbus/channel-value" in paths
    assert "/modbus/coil-test/plan" in paths
    assert "/modbus/coil-test/pulse" in paths
    assert "/modbus/coil-test/stop" in paths


def test_coil_pulse_role_is_enforced_server_side() -> None:
    assert modbus_hw.require_coil_test_role("system") == "system"
    assert modbus_hw.require_coil_test_role("admin") == "admin"
    with pytest.raises(OqlosError) as exc:
        modbus_hw.require_coil_test_role("operator")
    assert exc.value.status_code == 403
    assert exc.value.public_code == "C2004-AUTH-0002"
    assert exc.value.issue_code == "api_modbus_coil_pulse_forbidden"


def test_coil_pulse_role_denial_is_safe_problem_details() -> None:
    app = FastAPI()
    install_oqlos_error_handler(app)
    app.include_router(modbus_hw.router, prefix="/api/v1/hardware")

    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/hardware/modbus/coil-test/pulse",
        json={"coil": 1, "password": "hunter2"},
        headers={
            "X-Connect-Role": "password=hunter2",
            "X-Correlation-ID": "cor-coil-role",
        },
    )

    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "C2004-AUTH-0002"
    assert body["correlation_id"] == "cor-coil-role"
    assert body["component"] == "modbus-coil-test"
    assert body["stage"] == "role.authorize"
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "api_modbus_coil_pulse_forbidden"
    )
    assert "hunter2" not in response.text


def test_settings_put_applies_only_selected_runtime_profile(monkeypatch) -> None:
    calls: list[set[str]] = []

    class _Gateway:
        async def apply_modbus_user_settings(self, plugin_ids: set[str]):
            calls.append(plugin_ids)
            return {"ok": True, "actuation": False}

    monkeypatch.setattr(
        modbus_hw,
        "write_modbus_baud_settings",
        lambda _settings, _payload: {"active_profile": "modbus-io"},
    )
    monkeypatch.setattr(modbus_hw, "try_get_hardware_gateway", lambda: _Gateway())

    result = asyncio.run(
        modbus_hw.hardware_modbus_settings_put(
            {"profile_id": "modbus-io", "target_baudrate": 4800}
        )
    )

    assert calls == [{"modbus-io"}]
    assert result["runtime_apply"]["actuation"] is False


def test_wizard_rejects_missing_confirmation_before_pausing_plugin(monkeypatch) -> None:
    async def _unexpected_pause(_serial_port: str):
        raise AssertionError("plugin must not be paused before safety confirmation")

    monkeypatch.setattr(modbus_hw, "_pause_modbus_plugins_on_serial", _unexpected_pause)
    monkeypatch.setattr(
        modbus_hw,
        "_modbus_wizard_program_isolated",
        lambda **_kwargs: {"ok": False, "verified": False, "error": "confirmation required"},
    )

    with pytest.raises(OqlosError) as exc:
        asyncio.run(
            modbus_hw.hardware_modbus_wizard_program_isolated(
                serial_port="/dev/ttyTEST",
                current_device_id=1,
                new_device_id=1,
                new_baudrate=4800,
                new_parity="N",
                confirm_isolated=False,
                current_baudrate=4800,
            )
        )

    assert exc.value.status_code == 422
    assert exc.value.public_code == "C2004-DATA-0002"
    assert exc.value.issue_code == "api_modbus_wizard_invalid_request"


def test_wizard_verification_failure_is_safe_problem_details(monkeypatch) -> None:
    async def _pause(_serial_port: str):
        return None, set()

    monkeypatch.setattr(modbus_hw, "try_get_hardware_gateway", lambda: None)
    monkeypatch.setattr(modbus_hw, "_pause_modbus_plugins_on_serial", _pause)
    monkeypatch.setattr(
        modbus_hw,
        "_modbus_wizard_program_isolated",
        lambda **_kwargs: {
            "ok": False,
            "verified": False,
            "error": "password=hunter2 must not escape",
        },
    )
    app = FastAPI()
    install_oqlos_error_handler(app)
    app.include_router(modbus_hw.router, prefix="/api/v1/hardware")

    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/hardware/modbus/wizard/program-isolated",
        json={
            "serial_port": "/dev/ttyTEST",
            "confirm_isolated": True,
        },
        headers={"X-Correlation-ID": "cor-wizard-contract"},
    )

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "C2004-HW-0012"
    assert body["correlation_id"] == "cor-wizard-contract"
    assert body["component"] == "modbus-wizard"
    assert body["stage"] == "program.verify"
    assert body["metadata"]["context"]["problem_source"] == "upstream"
    assert body["metadata"]["context"]["upstream_target"] == (
        "serial-device://ttyTEST"
    )
    assert "hunter2" not in response.text
    assert "traceback" not in response.text.lower()
