"""Guards for valve output module selection (modbus-io vs M5 4In8Out)."""

from __future__ import annotations

from typing import Any

import pytest

from oqlos.hardware import valve_controller
from oqlos.hardware.valve_controller import (
    M5_VALVE_CONTROLLER,
    MODBUS_VALVE_CONTROLLER,
    resolve_valve_controller,
    resolve_valve_controllers,
    valve_controller_preference,
)


class _Config:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled


def _configs(**enabled: bool) -> dict[str, Any]:
    return {plugin_id: _Config(state) for plugin_id, state in enabled.items()}


@pytest.fixture(autouse=True)
def _no_ambient_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in valve_controller.VALVE_CONTROLLER_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(valve_controller, "_configured_preference", lambda: [])


def test_modbus_only_stand_keeps_using_modbus() -> None:
    configs = _configs(**{MODBUS_VALVE_CONTROLLER: True, M5_VALVE_CONTROLLER: False})

    assert resolve_valve_controller(configs) == MODBUS_VALVE_CONTROLLER
    assert resolve_valve_controllers(configs) == [MODBUS_VALVE_CONTROLLER]


def test_enabling_m5_makes_it_the_valve_controller() -> None:
    configs = _configs(**{MODBUS_VALVE_CONTROLLER: True, M5_VALVE_CONTROLLER: True})

    assert resolve_valve_controller(configs) == M5_VALVE_CONTROLLER
    # modbus-io stays as fallback for a stand mid-migration
    assert resolve_valve_controllers(configs) == [
        M5_VALVE_CONTROLLER,
        MODBUS_VALVE_CONTROLLER,
    ]


def test_no_enabled_controller_yields_no_candidates() -> None:
    configs = _configs(**{MODBUS_VALVE_CONTROLLER: False, M5_VALVE_CONTROLLER: False})

    assert resolve_valve_controllers(configs) == []
    # The single-id helper still names a controller for error messages.
    assert resolve_valve_controller(configs) == MODBUS_VALVE_CONTROLLER


def test_env_override_pins_the_controller(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OQLOS_VALVE_CONTROLLER", MODBUS_VALVE_CONTROLLER)
    configs = _configs(**{MODBUS_VALVE_CONTROLLER: True, M5_VALVE_CONTROLLER: True})

    assert resolve_valve_controller(configs) == MODBUS_VALVE_CONTROLLER


def test_pinned_controller_keeps_the_other_as_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OQLOS_VALVE_CONTROLLER", M5_VALVE_CONTROLLER)

    assert valve_controller_preference() == [
        M5_VALVE_CONTROLLER,
        MODBUS_VALVE_CONTROLLER,
    ]


def test_configuration_profile_selects_controller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        valve_controller,
        "_configured_preference",
        lambda: [MODBUS_VALVE_CONTROLLER],
    )
    configs = _configs(**{MODBUS_VALVE_CONTROLLER: True, M5_VALVE_CONTROLLER: True})

    assert resolve_valve_controller(configs) == MODBUS_VALVE_CONTROLLER


def test_unknown_plugin_ids_are_ignored() -> None:
    configs = _configs(**{MODBUS_VALVE_CONTROLLER: True})

    assert resolve_valve_controllers(configs) == [MODBUS_VALVE_CONTROLLER]


def test_gateway_controllers_come_from_the_live_plugin_configuration() -> None:
    class _Gateway:
        def valve_controllers(self) -> list[str]:
            return [M5_VALVE_CONTROLLER, MODBUS_VALVE_CONTROLLER]

    assert valve_controller.gateway_valve_controllers(_Gateway()) == [
        M5_VALVE_CONTROLLER,
        MODBUS_VALVE_CONTROLLER,
    ]


def test_gateway_without_plugin_configs_falls_back_to_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        valve_controller,
        "resolve_valve_controller_from_config",
        lambda: MODBUS_VALVE_CONTROLLER,
    )

    # Mock gateways used by scenario runs expose no plugin configuration.
    assert valve_controller.gateway_valve_controllers(object()) == [
        MODBUS_VALVE_CONTROLLER
    ]


def test_gateway_with_no_enabled_controller_reports_none() -> None:
    class _Gateway:
        def valve_controllers(self) -> list[str]:
            return []

    assert valve_controller.gateway_valve_controllers(_Gateway()) == []


def test_valve_targets_follow_the_configured_controller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from oqlos.hardware import peripheral_mapping

    monkeypatch.setattr(
        peripheral_mapping,
        "resolve_valve_controller_from_config",
        lambda: M5_VALVE_CONTROLLER,
    )

    assert peripheral_mapping.resolve_target_to_plugin("zawór-nc") == M5_VALVE_CONTROLLER
    assert peripheral_mapping.resolve_target_to_plugin("valve-3") == M5_VALVE_CONTROLLER
    # non-valve targets are untouched
    assert peripheral_mapping.resolve_target_to_plugin("pompa 1") == "motor-dri0050"
