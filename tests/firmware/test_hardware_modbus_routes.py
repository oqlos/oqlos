"""Regression tests for extracted Modbus HTTP routes."""

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
