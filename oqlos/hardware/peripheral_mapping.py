"""
Peripheral name mapping using plugin configuration.

This replaces the static _PERIPHERAL_MAP in firmware_adapter.py with a
plugin-based configuration system that is more flexible and maintainable.
"""

from __future__ import annotations

from oqlos.hardware.valve_controller import (
    DEFAULT_VALVE_CONTROLLER_PREFERENCE,
    resolve_valve_controller_from_config,
)

#: Plugin ids that can act as the valve output stage (resolved at call time).
VALVE_CONTROLLER_PLUGIN_IDS = frozenset(DEFAULT_VALVE_CONTROLLER_PREFERENCE)


# DSL target names → plugin ID mapping
# This maps DSL peripheral names to their corresponding plugin IDs
_PERIPHERAL_TO_PLUGIN_MAP = {
    # Pump targets
    "pump": "motor-dri0050",
    "pump-main": "motor-dri0050",
    "pump_main": "motor-dri0050",
    "pompa": "motor-dri0050",
    "pompa 1": "motor-dri0050",
    "pompa 2": "motor-dri0050",
    "pompa-1": "motor-dri0050",
    "pompa-2": "motor-dri0050",
    "pompa-kalibracyjna": "motor-dri0050",
    "pompa-testowa": "motor-dri0050",
    "pompa-próżniowa": "motor-dri0050",
    "pompa-ciśnieniowa": "motor-dri0050",
    "pompa-podciśnieniowa": "motor-dri0050",
    "compressor": "motor-dri0050",
    "sprężarka": "motor-dri0050",

    # Valve targets
    "valve": "modbus-io",
    "valve-inlet": "modbus-io",
    "valve_inlet": "modbus-io",
    "valve-outlet": "modbus-io",
    "valve_outlet": "modbus-io",
    "zawór-izolacyjny": "modbus-io",
    "zawor-izolacyjny": "modbus-io",
    "zawór-wlotowy": "modbus-io",
    "zawor-wlotowy": "modbus-io",
    "zawór-wylotowy": "modbus-io",
    "zawor-wylotowy": "modbus-io",

    # Circuit valves (NC/SC/WC)
    "valve-nc": "modbus-io",
    "valve-sc": "modbus-io",
    "valve-wc": "modbus-io",
    "zawór-nc": "modbus-io",
    "zawór-sc": "modbus-io",
    "zawór-wc": "modbus-io",
    "zawor-nc": "modbus-io",
    "zawor-sc": "modbus-io",
    "zawor-wc": "modbus-io",

    # Dynamic valve numbering
    "valve-overpressure": "modbus-io",
    "zawór-overpressure": "modbus-io",
    "zawor-overpressure": "modbus-io",
    "overpressure": "modbus-io",
    "zawór-butli": "modbus-io",
    "zawor-butli": "modbus-io",
    "valve-butli": "modbus-io",
    "bottle-valve": "modbus-io",

    # Lung targets
    "lung": "motor-tic249",
    "lung-main": "motor-tic249",
    "płuco": "motor-tic249",
    "pluco": "motor-tic249",
    "sztuczne_pluco": "motor-tic249",
    "sztuczne pluco": "motor-tic249",
    "sztuczne płuco": "motor-tic249",

    # Sensor targets
    "nc-sensor": "modbus-adc",
    "nc_sensor": "modbus-adc",
    "ciśnienie-nc": "modbus-adc",
    "cisnienie-nc": "modbus-adc",
    "nadciśnienie": "modbus-adc",
    "nadcisnienie": "modbus-adc",
    "AI01": "modbus-adc",

    "sc-sensor": "modbus-adc",
    "ciśnienie-sc": "modbus-adc",
    "cisnienie-sc": "modbus-adc",
    "AI02": "modbus-adc",

    "wc-sensor": "modbus-adc",
    "ciśnienie-wc": "modbus-adc",
    "cisnienie-wc": "modbus-adc",
    "AI03": "modbus-adc",

    "pressure-sensor": "modbus-adc",
    "pressure_sensor": "modbus-adc",
}


def resolve_target_to_plugin(target: str) -> str | None:
    """
    Resolve a DSL target name to its plugin ID.

    Valve targets are resolved against the configured valve output module, so a
    stand rewired from the Waveshare RS485 module to the M5Stack 4In8Out module
    keeps working without touching this table.

    Args:
        target: The DSL target name (e.g., "pompa 1", "zawór NC")

    Returns:
        The plugin ID (e.g., "motor-dri0050", "modbus-io") or None if not found
    """
    plugin_id = _PERIPHERAL_TO_PLUGIN_MAP.get(target)
    if plugin_id in VALVE_CONTROLLER_PLUGIN_IDS:
        return resolve_valve_controller_from_config()
    return plugin_id


def register_custom_mapping(target: str, plugin_id: str) -> None:
    """
    Register a custom peripheral-to-plugin mapping.

    This allows runtime configuration of new peripheral names.
    """
    _PERIPHERAL_TO_PLUGIN_MAP[target] = plugin_id


def get_all_mappings() -> dict[str, str]:
    """Get all peripheral-to-plugin mappings."""
    return dict(_PERIPHERAL_TO_PLUGIN_MAP)


def generate_dynamic_valve_mappings(max_valve_count: int = 15) -> None:
    """
    Generate dynamic valve mappings for numbered valves.

    This is called during initialization to create mappings for valve-1 through valve-N.
    """
    for i in range(1, max_valve_count + 1):
        _PERIPHERAL_TO_PLUGIN_MAP[f"valve-{i}"] = "modbus-io"
        _PERIPHERAL_TO_PLUGIN_MAP[f"valve_{i}"] = "modbus-io"
        _PERIPHERAL_TO_PLUGIN_MAP[f"zawór-{i}"] = "modbus-io"
        _PERIPHERAL_TO_PLUGIN_MAP[f"zawor-{i}"] = "modbus-io"


# Initialize dynamic mappings
generate_dynamic_valve_mappings()
