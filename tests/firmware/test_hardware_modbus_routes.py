"""Regression tests for extracted Modbus HTTP routes."""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oqlos.api import hardware_modbus_routes as modbus_hw
from oqlos.errors import OqlosError
from oqlos.errors.fastapi_integration import install_oqlos_error_handler


def _modbus_client() -> TestClient:
    app = FastAPI()
    install_oqlos_error_handler(app)
    app.include_router(modbus_hw.router, prefix="/api/v1/hardware")
    return TestClient(app, raise_server_exceptions=False)


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
    response = _modbus_client().post(
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
    response = _modbus_client().post(
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
    assert body["metadata"]["context"]["problem_source"] == "hardware"
    assert body["metadata"]["context"]["upstream_target"] == (
        "serial-device://ttyTEST"
    )
    assert "hunter2" not in response.text
    assert "traceback" not in response.text.lower()


def test_wizard_probe_no_match_is_not_http_200(monkeypatch) -> None:
    monkeypatch.setattr(
        modbus_hw,
        "_modbus_wizard_probe_isolated",
        lambda *_args, **_kwargs: {
            "ok": False,
            "error": "password=hunter2",
            "all_scans": [{"serial_port": "/dev/password=hunter2"}],
        },
    )

    response = _modbus_client().post(
        "/api/v1/hardware/modbus/wizard/probe-isolated",
        json={"serial_port": "/dev/ttyTEST", "module_role": "io"},
        headers={"X-Correlation-ID": "cor-wizard-probe"},
    )

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "C2004-HW-0012"
    assert body["correlation_id"] == "cor-wizard-probe"
    assert body["stage"] == "probe.scan"
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "hw_modbus_no_response"
    )
    assert body["metadata"]["context"]["upstream_target"] == (
        "serial-device://ttyTEST"
    )
    assert "hunter2" not in response.text


def test_wizard_probe_exception_is_sanitized(monkeypatch) -> None:
    def _fail(*_args, **_kwargs):
        raise OSError("password=hunter2 /srv/private")

    monkeypatch.setattr(modbus_hw, "_modbus_wizard_probe_isolated", _fail)

    response = _modbus_client().post(
        "/api/v1/hardware/modbus/wizard/probe-isolated",
        json={"serial_port": "/dev/password=hunter2"},
        headers={"X-Correlation-ID": "cor-wizard-probe"},
    )

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "C2004-HW-0012"
    assert body["stage"] == "probe.execute"
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "modbus_preflight_exception"
    )
    assert body["metadata"]["context"]["upstream_target"] == (
        "serial-device://configured-adapter"
    )
    assert "hunter2" not in response.text
    assert "/srv/private" not in response.text


def test_wizard_probe_busy_port_keeps_specific_contract(monkeypatch) -> None:
    def _fail(*_args, **_kwargs):
        raise OSError("serial port is busy password=hunter2")

    monkeypatch.setattr(modbus_hw, "_modbus_wizard_probe_isolated", _fail)

    response = _modbus_client().post(
        "/api/v1/hardware/modbus/wizard/probe-isolated",
        json={"serial_port": "/dev/ttyTEST"},
        headers={"X-Correlation-ID": "cor-wizard-busy"},
    )

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "C2004-HW-0013"
    assert body["correlation_id"] == "cor-wizard-busy"
    assert body["stage"] == "probe.execute"
    assert body["metadata"]["diagnostics"]["issue_code"] == "serial_port_busy"
    assert "hunter2" not in response.text


def test_wizard_probe_missing_pimodbus_is_safe_problem(monkeypatch) -> None:
    from oqlos.api.hardware_modbus_wizard_boundary import (
        _raise_pimodbus_unavailable,
    )

    def _fail(*_args, **_kwargs):
        _raise_pimodbus_unavailable(
            operation_id="modbus.wizard.probe-isolated",
            cause=ModuleNotFoundError("password=hunter2 /srv/private"),
        )

    monkeypatch.setattr(modbus_hw, "_modbus_wizard_probe_isolated", _fail)

    response = _modbus_client().post(
        "/api/v1/hardware/modbus/wizard/probe-isolated",
        json={"serial_port": "/dev/ttyTEST"},
        headers={"X-Correlation-ID": "cor-wizard-dependency"},
    )

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "C2004-HW-0012"
    assert body["correlation_id"] == "cor-wizard-dependency"
    assert body["stage"] == "dependency.load"
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "pimodbus_unavailable"
    )
    assert body["metadata"]["context"]["upstream_target"] == (
        "python-package://pimodbus"
    )
    assert "hunter2" not in response.text
    assert "/srv/private" not in response.text


def test_waveshare_busy_adapter_is_safe_problem_details(monkeypatch) -> None:
    from oqlos.api.hardware_modbus_waveshare_boundary import (
        _raise_waveshare_probe_failure,
    )

    def _fail(_health):
        _raise_waveshare_probe_failure(
            serial_port="/dev/password=hunter2",
            cause=OSError("serial port is busy password=hunter2 /srv/private"),
        )

    async def _snapshot(build_fn):
        return build_fn(None)

    monkeypatch.setattr(modbus_hw, "_build_waveshare_diagnose_report", _fail)
    monkeypatch.setattr(modbus_hw, "snapshot_via_health", _snapshot)

    response = _modbus_client().get(
        "/api/v1/hardware/modbus/waveshare-diagnose",
        headers={"X-Correlation-ID": "cor-waveshare-busy"},
    )

    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "C2004-HW-0013"
    assert body["correlation_id"] == "cor-waveshare-busy"
    assert body["component"] == "modbus-waveshare"
    assert body["stage"] == "matrix.scan"
    assert body["metadata"]["diagnostics"]["issue_code"] == "serial_port_busy"
    assert body["metadata"]["context"]["upstream_target"] == (
        "serial-device://configured-adapter"
    )
    assert "hunter2" not in response.text
    assert "/srv/private" not in response.text


def test_wizard_probe_rejects_role_without_reflecting_it() -> None:
    response = _modbus_client().post(
        "/api/v1/hardware/modbus/wizard/probe-isolated",
        json={"module_role": "password=hunter2"},
        headers={"X-Correlation-ID": "cor-wizard-role"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "C2004-DATA-0002"
    assert body["correlation_id"] == "cor-wizard-role"
    assert body["stage"] == "request.validate"
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "api_modbus_wizard_invalid_request"
    )
    assert "hunter2" not in response.text


def test_wizard_program_exception_is_sanitized(monkeypatch) -> None:
    async def _pause(_serial_port: str):
        return None, set()

    def _fail(**_kwargs):
        raise OSError("password=hunter2 /srv/private")

    monkeypatch.setattr(modbus_hw, "try_get_hardware_gateway", lambda: None)
    monkeypatch.setattr(modbus_hw, "_pause_modbus_plugins_on_serial", _pause)
    monkeypatch.setattr(modbus_hw, "_modbus_wizard_program_isolated", _fail)

    response = _modbus_client().post(
        "/api/v1/hardware/modbus/wizard/program-isolated",
        json={
            "serial_port": "/dev/password=hunter2",
            "confirm_isolated": True,
        },
        headers={"X-Correlation-ID": "cor-wizard-program"},
    )

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "C2004-HW-0012"
    assert body["correlation_id"] == "cor-wizard-program"
    assert body["stage"] == "program.execute"
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "modbus_preflight_exception"
    )
    assert body["metadata"]["context"]["upstream_target"] == (
        "serial-device://configured-adapter"
    )
    assert "hunter2" not in response.text
    assert "/srv/private" not in response.text


def test_wizard_programming_error_is_not_masked_and_plugins_resume(monkeypatch) -> None:
    resumed: list[set[str]] = []

    class _Gateway:
        async def apply_modbus_user_settings(self, plugin_ids: set[str]):
            resumed.append(plugin_ids)
            return {"ok": True, "actuation": False}

    async def _pause(_serial_port: str):
        return _Gateway(), {"modbus-io"}

    def _fail(**_kwargs):
        raise AttributeError("password=hunter2 /srv/private")

    monkeypatch.setattr(modbus_hw, "try_get_hardware_gateway", lambda: None)
    monkeypatch.setattr(modbus_hw, "_pause_modbus_plugins_on_serial", _pause)
    monkeypatch.setattr(modbus_hw, "_modbus_wizard_program_isolated", _fail)

    response = _modbus_client().post(
        "/api/v1/hardware/modbus/wizard/program-isolated",
        json={"serial_port": "/dev/ttyTEST", "confirm_isolated": True},
        headers={"X-Correlation-ID": "cor-wizard-programming-error"},
    )

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "C2004-SYS-0000"
    assert body["correlation_id"] == "cor-wizard-programming-error"
    assert resumed == [{"modbus-io"}]
    assert "hunter2" not in response.text
    assert "/srv/private" not in response.text
