"""Regression tests for extracted Modbus HTTP routes."""

import asyncio

import pytest
from fastapi import HTTPException

from oqlos.api import hardware_modbus_routes as modbus_hw
from oqlos.errors import OqlosError


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
    with pytest.raises(HTTPException) as exc:
        modbus_hw.require_coil_test_role("operator")
    assert exc.value.status_code == 403
    assert exc.value.detail["error_code"] == "C2004-AUTH-0002"
    assert exc.value.detail["c2004_code"] == "C2004-AUTH-0002"


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
