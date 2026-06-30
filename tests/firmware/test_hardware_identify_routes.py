"""Regression tests for extracted identify/health routes."""

from oqlos.api import hardware as hw


def test_hardware_router_includes_health_and_identify():
    paths = {route.path for route in hw.router.routes}
    assert "/api/v1/hardware/health" in paths
    assert "/api/v1/hardware/identify" in paths
