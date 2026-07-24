"""Regression: v3 system routes for Modbus, RTC, and motor-scoped diagnosis."""

from oqlos.api._hw3_system import sub_router


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
