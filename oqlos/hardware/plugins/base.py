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
from enum import Enum
from typing import Any, ClassVar

import pluggy
from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator


class PluginStatus(Enum):
    """Status of a hardware plugin."""
    UNKNOWN = "unknown"
    CONFIGURED = "configured"
    CONNECTED = "connected"
    ERROR = "error"
    INCOMPATIBLE = "incompatible"


# ---------------------------------------------------------------------------
# Pluggy hook markers — used by third-party driver packages
# ---------------------------------------------------------------------------
hookspec = pluggy.HookspecMarker("oqlos_hardware")
hookimpl = pluggy.HookimplMarker("oqlos_hardware")


class HardwareDriverSpec:
    """
    Pluggy hookspec for hardware drivers.

    Third-party drivers implement these hooks and register via the
    ``oqlos_hardware`` entry point group, e.g.::

        pip install oqlos-driver-dri0050

    with entry point::

        [project.entry-points."oqlos_hardware"]
        dri0050 = "oqlos_driver_dri0050:DRIPumpDriver"

    Built-in plugins still use the HardwarePlugin ABC — the hookspec
    is an *additional* integration path for external packages.
    """

    @hookspec
    def set_peripheral(self, peripheral_id: str, value: float, mode: str) -> dict[str, Any]:
        """Set a peripheral value (pump speed, valve state, …)."""

    @hookspec
    def read_sensor(self, sensor_id: str) -> dict[str, Any]:
        """Read a sensor value."""

    @hookspec
    def get_driver_status(self) -> dict[str, Any]:
        """Return driver health / diagnostic information."""


# Singleton PluginManager for the hookspec
_pluggy_pm = pluggy.PluginManager("oqlos_hardware")
_pluggy_pm.add_hookspecs(HardwareDriverSpec)


def get_pluggy_manager() -> pluggy.PluginManager:
    """Return the global pluggy PluginManager for third-party drivers."""
    return _pluggy_pm


# ---------------------------------------------------------------------------
# Pydantic configuration models
# ---------------------------------------------------------------------------

class ScaleConfig(BaseModel):
    """Scale / range definition for a peripheral parameter."""
    min: float = 0
    max: float = 100
    default: float | None = None
    unit: str = ""

    def contains(self, value: float) -> bool:
        """Check if *value* is within [min, max]."""
        return self.min <= value <= self.max

    def clamp(self, value: float) -> float:
        """Clamp *value* to [min, max]."""
        return max(self.min, min(self.max, value))


class ConversionConfig(BaseModel):
    """Describes how to convert a logical value to a hardware value."""
    type: str = "none"              # none | linear | lookup
    scale: float = 1.0
    offset: float = 0.0
    lookup: dict[str, float] = Field(default_factory=dict)


class PeripheralConfig(BaseModel):
    """
    Configuration for a single peripheral (sensor / actuator).

    Loaded from the ``peripherals:`` section of the plugin YAML config.
    """
    name: str
    type: str = ""                  # pump, valve, sensor, …
    scale: ScaleConfig = Field(default_factory=ScaleConfig)
    conversion: ConversionConfig = Field(default_factory=ConversionConfig)
    raster: list[float] | None = None
    properties: dict[str, Any] = Field(default_factory=dict)

    def validate_value(self, value: float) -> tuple[bool, str]:
        """Validate *value* against raster and scale range."""
        if self.raster is not None and value not in self.raster:
            return False, f"Value {value} not in allowed raster: {self.raster}"
        if not self.scale.contains(value):
            return False, (
                f"Value {value} out of range [{self.scale.min}, {self.scale.max}]"
            )
        return True, ""

    def convert_value(self, value: float) -> float:
        """Apply configured conversion (linear / lookup / identity)."""
        c = self.conversion
        if c.type == "linear":
            return value * c.scale + c.offset
        if c.type == "lookup" and c.lookup:
            closest = min(c.lookup, key=lambda k: abs(float(k) - value))
            return c.lookup[closest]
        return value


class PluginConfig(BaseModel):
    """Standardized configuration schema for hardware plugins."""
    plugin_id: str
    enabled: bool = True
    connection_type: str = "http"   # http, serial, gpio, i2c, spi, etc.
    connection_params: dict[str, Any] = Field(default_factory=dict)
    timeout: float = 5.0
    retry_count: int = 3
    metadata: dict[str, Any] = Field(default_factory=dict)
    peripherals: dict[str, PeripheralConfig] = Field(default_factory=dict)

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors (empty if valid)."""
        errors: list[str] = []
        if not self.plugin_id:
            errors.append("plugin_id is required")
        if self.timeout <= 0:
            errors.append("timeout must be positive")
        if self.retry_count < 0:
            errors.append("retry_count must be non-negative")
        return errors

    def get_peripheral(self, name: str) -> PeripheralConfig | None:
        """Look up a peripheral configuration by name."""
        return self.peripherals.get(name)


class OqlosConfigDocument(BaseModel):
    """Top-level ``oqlos.yaml`` schema.

    Keeps plugin map dynamic (`dict[str, PluginConfig]`) and allows extra
    top-level sections for forward-compatible evolution.
    """

    model_config = ConfigDict(extra="allow")
    plugins: dict[str, PluginConfig] = Field(default_factory=dict)

    @field_validator("plugins", mode="before")
    @classmethod
    def _inject_plugin_ids(
        cls,
        value: Any,
    ) -> dict[str, dict[str, Any]]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            return value

        normalized: dict[str, dict[str, Any]] = {}
        for plugin_id, plugin_data in value.items():
            if isinstance(plugin_data, dict):
                normalized[plugin_id] = {"plugin_id": plugin_id, **plugin_data}
            else:
                normalized[plugin_id] = plugin_data
        return normalized


class PluginHealth(BaseModel):
    """Health check result for a hardware plugin."""
    status: PluginStatus
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    compatible: bool = True
    version: str = "unknown"
    last_check: str = ""


def dynamic_peripheral_model(
    peripheral: PeripheralConfig,
    *,
    model_name: str | None = None,
) -> type[BaseModel]:
    """
    Generate a runtime Pydantic model from a ``PeripheralConfig``.

    Extra fields listed in ``peripheral.properties`` become typed model
    attributes.  The ``value`` field carries the configured scale
    constraints as metadata.

    Usage::

        cfg = PluginConfig.model_validate(yaml_dict)
        SpeedModel = dynamic_peripheral_model(cfg.peripherals["speed"])
        instance = SpeedModel(value=50)      # validates against scale
        print(instance.model_dump())

    Returns:
        A Pydantic ``BaseModel`` subclass.
    """
    name = model_name or f"{peripheral.name.title().replace(' ', '')}Peripheral"
    fields: dict[str, Any] = {
        "value": (
            float,
            Field(
                default=peripheral.scale.default or 0,
                ge=peripheral.scale.min,
                le=peripheral.scale.max,
                description=f"{peripheral.name} ({peripheral.scale.unit})",
            ),
        ),
        "unit": (str, Field(default=peripheral.scale.unit)),
    }
    # Merge custom properties from YAML as optional fields
    for prop_name, prop_default in peripheral.properties.items():
        prop_type = type(prop_default) if prop_default is not None else Any
        fields[prop_name] = (prop_type, Field(default=prop_default))

    return create_model(name, **fields)


def dynamic_plugin_schema_models(config: PluginConfig) -> dict[str, type[BaseModel]]:
    """Build runtime Pydantic models for all plugin peripherals.

    Returns mapping ``peripheral_name -> dynamic model class`` generated from
    ``PeripheralConfig`` definitions in ``oqlos.yaml``.
    """
    models: dict[str, type[BaseModel]] = {}
    for peripheral_name, peripheral in config.peripherals.items():
        model_name = (
            f"{config.plugin_id.title().replace('-', '')}"
            f"{peripheral_name.title().replace('-', '').replace('_', '')}Schema"
        )
        models[peripheral_name] = dynamic_peripheral_model(peripheral, model_name=model_name)
    return models


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
