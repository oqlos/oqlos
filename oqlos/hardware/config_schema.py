"""
Hardware configuration schema — **deprecated bridge**.

Prefer importing directly from ``oqlos.hardware.plugins.base``::

    from oqlos.hardware.plugins import (
        PluginConfig, PeripheralConfig, ScaleConfig, ConversionConfig,
    )

This module is kept for backward compatibility.  It re-exports the
canonical Pydantic models from ``plugins.base`` and provides helper
functions (``get_hardware_config``, ``register_hardware_config``,
``load_config_from_yaml``) that delegate to the unified YAML-driven
plugin system.
"""

from __future__ import annotations

import logging
import warnings
from enum import Enum
from pathlib import Path
from typing import Any

from oqlos.hardware.plugins.base import (
    ConversionConfig,
    PeripheralConfig,
    PluginConfig,
    ScaleConfig,
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
    """Return the PluginConfig for *device_id* (loaded from unified YAML).

    .. deprecated::
        Use ``PluginRegistry.load_configs_from_yaml()`` and access
        ``PluginConfig.peripherals`` directly.
    """
    warnings.warn(
        "get_hardware_config() is deprecated — use PluginConfig.peripherals",
        DeprecationWarning,
        stacklevel=2,
    )
    default_yaml = Path(__file__).parent / "hardware_config.yaml"
    if default_yaml.exists():
        configs = PluginRegistry.load_configs_from_yaml(default_yaml)
        return configs.get(device_id)
    return None


def register_hardware_config(config: PluginConfig) -> None:
    """No-op shim — configs live in the unified YAML now.

    .. deprecated::
        Edit ``hardware_config.yaml`` and call
        ``PluginRegistry.load_configs_from_yaml()`` instead.
    """
    warnings.warn(
        "register_hardware_config() is deprecated — edit hardware_config.yaml",
        DeprecationWarning,
        stacklevel=2,
    )


def load_config_from_yaml(
    config_path: str | Path,
) -> dict[str, PluginConfig]:
    """Load plugin configs from the **unified** YAML format.

    .. deprecated::
        Use ``PluginRegistry.load_configs_from_yaml()`` directly.
    """
    warnings.warn(
        "load_config_from_yaml() is deprecated — use PluginRegistry.load_configs_from_yaml()",
        DeprecationWarning,
        stacklevel=2,
    )
    return PluginRegistry.load_configs_from_yaml(config_path)
