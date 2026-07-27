"""
Hardware configuration schema — **deprecated bridge**.

Prefer importing directly from ``oqlos.hardware.plugins.base``::

    from oqlos.hardware.plugins import (
        PluginConfig, PeripheralConfig, ScaleConfig, ConversionConfig,
    )

This module is kept for backward compatibility.  It re-exports the
canonical Pydantic models from ``plugins.base`` and provides helper
functions (``get_hardware_config``, ``register_hardware_config``,
``load_config_from_yaml``) that delegate to the versioned format-neutral
plugin configuration.
"""

from __future__ import annotations

import logging
import warnings
from enum import Enum
from pathlib import Path

from pydantic import BaseModel

from oqlos.hardware.config_paths import resolve_oqlos_config_path
from oqlos.hardware.plugins.base import (
    PluginConfig,
    dynamic_plugin_schema_models,
)
from oqlos.hardware.plugins.registry import PluginRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# UnitType enum — still the canonical source for unit labels
# ---------------------------------------------------------------------------

class UnitType(Enum):
    """Standard unit types for hardware parameters."""
    # Flow rate
    LITERS_PER_MINUTE = "l/min"
    MILLILITERS_PER_MINUTE = "ml/min"
    CUBIC_METERS_PER_HOUR = "m3/h"
    # Pressure
    BAR = "bar"
    PASCAL = "Pa"
    MILLIBAR = "mbar"
    PSI = "psi"
    # Power
    PERCENT = "%"
    WATT = "W"
    # Temperature
    CELSIUS = "C"
    FAHRENHEIT = "F"
    KELVIN = "K"
    # Frequency
    HERTZ = "Hz"
    KILOHERTZ = "kHz"
    # Time
    SECOND = "s"
    MILLISECOND = "ms"
    MINUTE = "min"
    # Voltage
    VOLT = "V"
    MILLIVOLT = "mV"
    # Current
    AMPERE = "A"
    MILLIAMPERE = "mA"
    # Dimensionless
    DIMENSIONLESS = ""


# ---------------------------------------------------------------------------
# Compatibility helpers — delegate to the unified plugin config
# ---------------------------------------------------------------------------

def get_hardware_config(device_id: str) -> PluginConfig | None:
    """Return the PluginConfig for *device_id* from the versioned configuration.

    .. deprecated::
        Use ``PluginRegistry.load_configs()`` and access
        ``PluginConfig.peripherals`` directly.
    """
    warnings.warn(
        "get_hardware_config() is deprecated — use PluginConfig.peripherals",
        DeprecationWarning,
        stacklevel=2,
    )
    try:
        config_path = resolve_oqlos_config_path()
    except FileNotFoundError:
        return None
    configs = PluginRegistry.load_configs(config_path)
    return configs.get(device_id)


def register_hardware_config(config: PluginConfig) -> None:
    """No-op shim — configs live in the active versioned document.

    .. deprecated::
        Edit ``oqlos.{oql,yaml,json}`` and call ``PluginRegistry.load_configs()``.
    """
    warnings.warn(
        "register_hardware_config() is deprecated — edit the active OqlOS config",
        DeprecationWarning,
        stacklevel=2,
    )


def load_config_from_yaml(
    config_path: str | Path,
) -> dict[str, PluginConfig]:
    """Load plugin configs from the **unified** YAML format.

    .. deprecated::
        Use ``PluginRegistry.load_configs()`` directly.
    """
    warnings.warn(
        "load_config_from_yaml() is deprecated — use PluginRegistry.load_configs()",
        DeprecationWarning,
        stacklevel=2,
    )
    return PluginRegistry.load_configs(config_path)


def build_dynamic_schema_models(
    config_path: str | Path | None = None,
) -> dict[str, dict[str, type[BaseModel]]]:
    """Build runtime Pydantic schema models from the active hardware configuration.

    Returns mapping ``plugin_id -> {peripheral_name -> model_class}``.
    """
    resolved_path = resolve_oqlos_config_path(config_path)
    configs = PluginRegistry.load_configs(resolved_path)
    return {
        plugin_id: dynamic_plugin_schema_models(plugin_config)
        for plugin_id, plugin_config in configs.items()
    }
