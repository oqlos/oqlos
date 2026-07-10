"""Regression tests for extracted Modbus HTTP routes."""

from oqlos.api import hardware_modbus_routes as modbus_hw


def test_hardware_modbus_router_includes_channel_and_wizard_paths():
    paths = {route.path for route in modbus_hw.router.routes}
    assert "/modbus/waveshare-diagnose" in paths
    assert "/modbus/wizard/plan" in paths
    assert "/modbus/wizard/probe-isolated" in paths
    assert "/modbus/wizard/program-isolated" in paths
    assert "/modbus/profile-channels" in paths
    assert "/modbus/channel-value" in paths
