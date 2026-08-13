"""
Hardware plugin system - standardized interface for hardware integrations.
"""

from .base import (
    ConversionConfig,
    HardwareDriverSpec,
    HardwarePlugin,
    OqlosConfigDocument,
    PeripheralConfig,
    PluginConfig,
    PluginHealth,
    PluginStatus,
    ScaleConfig,
    dynamic_plugin_schema_models,
    dynamic_peripheral_model,
    get_pluggy_manager,
    hookimpl,
    hookspec,
)
from .registry import PluginRegistry
from .piadc import PiadcPlugin
from .modbus_adc import ModbusAdcPlugin
from .motor import MotorPlugin
from .modbus import ModbusPlugin
from .m5_4in8out import M54In8OutPlugin
from .lung import LungPlugin

__all__ = [
    "ConversionConfig",
    "HardwareDriverSpec",
    "HardwarePlugin",
    "OqlosConfigDocument",
    "PeripheralConfig",
    "PluginConfig",
    "PluginHealth",
    "PluginStatus",
    "ScaleConfig",
    "dynamic_plugin_schema_models",
    "dynamic_peripheral_model",
    "get_pluggy_manager",
    "hookimpl",
    "hookspec",
    "PluginRegistry",
    "PiadcPlugin",
    "ModbusAdcPlugin",
    "MotorPlugin",
    "ModbusPlugin",
    "M54In8OutPlugin",
    "LungPlugin",
]
