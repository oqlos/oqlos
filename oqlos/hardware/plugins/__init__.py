"""
Hardware plugin system - standardized interface for hardware integrations.
"""

from .base import HardwarePlugin, PluginConfig, PluginHealth, PluginStatus
from .registry import PluginRegistry
from .piadc import PiadcPlugin
from .motor import MotorPlugin
from .modbus import ModbusPlugin
from .lung import LungPlugin

__all__ = [
    "HardwarePlugin",
    "PluginConfig",
    "PluginHealth",
    "PluginStatus",
    "PluginRegistry",
    "PiadcPlugin",
    "MotorPlugin",
    "ModbusPlugin",
    "LungPlugin",
]
