"""Regression tests for extracted Modbus HTTP routes."""

from oqlos.api import hardware as hw


def test_hardware_router_includes_modbus_paths():
    paths = {route.path for route in hw.router.routes}
    assert "/api/v1/hardware/modbus/waveshare-diagnose" in paths
    assert "/api/v1/hardware/modbus/wizard/plan" in paths
    assert "/api/v1/hardware/modbus/wizard/probe-isolated" in paths
    assert "/api/v1/hardware/modbus/wizard/program-isolated" in paths
