"""
Hardware plugin system - standardized interface for hardware integrations.

Each hardware integration (piadc, motor, lung, modbus, etc.) should be a plugin
that implements this interface, providing:
- Standardized configuration schema
- Health checks and validation
- Clear error messages for misconfiguration
- Discovery and registration
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar


class PluginStatus(Enum):
    """Status of a hardware plugin."""
    UNKNOWN = "unknown"
    CONFIGURED = "configured"
    CONNECTED = "connected"
    ERROR = "error"
    INCOMPATIBLE = "incompatible"


@dataclass
class PluginConfig:
    """Standardized configuration schema for hardware plugins."""
    plugin_id: str
    enabled: bool = True
    connection_type: str = "http"  # http, serial, gpio, i2c, spi, etc.
    connection_params: dict[str, Any] = field(default_factory=dict)
    timeout: float = 5.0
    retry_count: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors (empty if valid)."""
        errors = []
        if not self.plugin_id:
            errors.append("plugin_id is required")
        if self.timeout <= 0:
            errors.append("timeout must be positive")
        if self.retry_count < 0:
            errors.append("retry_count must be non-negative")
        return errors


@dataclass
class PluginHealth:
    """Health check result for a hardware plugin."""
    status: PluginStatus
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    compatible: bool = True
    version: str = "unknown"
    last_check: str = ""


class HardwarePlugin(ABC):
    """
    Base interface for hardware integration plugins.

    Each plugin must:
    - Define its configuration schema
    - Implement health checks
    - Provide clear error messages
    - Support discovery and validation
    """

    # Class-level metadata (must be overridden by subclasses)
    PLUGIN_ID: ClassVar[str] = "unknown"
    PLUGIN_NAME: ClassVar[str] = "Unknown Plugin"
    PLUGIN_VERSION: ClassVar[str] = "1.0.0"
    PLUGIN_DESCRIPTION: ClassVar[str] = ""
    REQUIRED_PYTHON_PACKAGES: ClassVar[list[str]] = []
    SUPPORTED_PROTOCOLS: ClassVar[list[str]] = []

    def __init__(self, config: PluginConfig):
        self.config = config
        self._status = PluginStatus.UNKNOWN
        self._health = PluginHealth(status=PluginStatus.UNKNOWN)

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the hardware. Returns True if successful."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the hardware."""
        pass

    @abstractmethod
    async def health_check(self) -> PluginHealth:
        """
        Check if the hardware is accessible and properly configured.

        Should return:
        - status: CONNECTED if working, ERROR if not
        - message: clear description of any issues
        - details: diagnostic information
        - compatible: True if hardware is compatible with this plugin
        """
        pass

    @abstractmethod
    def validate_config(self) -> list[str]:
        """
        Validate the plugin configuration.

        Returns a list of error messages (empty if valid).
        Should check for:
        - Required parameters
        - Parameter types and ranges
        - Compatibility with hardware
        """
        pass

    @abstractmethod
    async def execute_command(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a hardware command.

        Args:
            command: The command to execute (e.g., "set_speed", "read_sensor")
            params: Command-specific parameters

        Returns:
            Result dictionary with at least 'success' boolean and 'data'/'error' fields.
        """
        pass

    @classmethod
    def get_capabilities(cls) -> dict[str, Any]:
        """
        Return plugin capabilities and metadata.

        Should include:
        - Supported commands
        - Supported parameters
        - Hardware requirements
        - Configuration schema
        """
        return {
            "plugin_id": cls.PLUGIN_ID,
            "name": cls.PLUGIN_NAME,
            "version": cls.PLUGIN_VERSION,
            "description": cls.PLUGIN_DESCRIPTION,
            "required_packages": cls.REQUIRED_PYTHON_PACKAGES,
            "supported_protocols": cls.SUPPORTED_PROTOCOLS,
        }

    @property
    def status(self) -> PluginStatus:
        return self._status

    @property
    def is_connected(self) -> bool:
        return self._status == PluginStatus.CONNECTED

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(plugin_id={self.PLUGIN_ID!r}, status={self._status.value})"
