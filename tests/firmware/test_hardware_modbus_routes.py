"""Regression tests for extracted Modbus HTTP routes."""

import asyncio

import pytest
from fastapi import HTTPException

from oqlos.api import hardware_modbus_routes as modbus_hw


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
