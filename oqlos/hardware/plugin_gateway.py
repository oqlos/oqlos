"""
Plugin-based Hardware Gateway - simplified architecture using hardware plugins.

This replaces the old HardwareGateway with hardcoded adapters by using the
new plugin system. All hardware communication goes through standardized plugins
with validated configuration and clear error reporting.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from oqlos.config import get_settings
from oqlos.hardware.plugins import (
    PluginConfig,
    PluginRegistry,
    PluginStatus,
    PiadcPlugin,
    MotorPlugin,
    ModbusPlugin,
    LungPlugin,
)

logger = logging.getLogger(__name__)

# Register built-in plugins
PluginRegistry.register(PiadcPlugin)
PluginRegistry.register(MotorPlugin)
PluginRegistry.register(ModbusPlugin)
PluginRegistry.register(LungPlugin)

# Discover third-party plugins from entry points
PluginRegistry.discover_entry_point_plugins()


class PluginHardwareGateway:
    """
    Simplified hardware gateway using plugin architecture.

    Instead of hardcoded adapters, this gateway uses the plugin system:
    - Plugins are loaded from configuration (YAML/ENV)
    - Each plugin handles its own connection and validation
    - Clear error messages for misconfiguration
    - Easy to add new hardware types
    """

    def __init__(self, mode: str | None = None, config_path: str | None = None):
        settings = get_settings()
        self.mode = mode or settings.hardware_mode.lower()
        self._plugins: dict[str, Any] = {}
        self._plugin_configs: dict[str, PluginConfig] = {}

        self._init_done = False
        if self.mode == "real":
            # Load hardware configuration schema
            self._load_hardware_schema()
            self._load_plugin_configs(config_path or settings)
            # Schedule async plugin init — will run on first await or event-loop tick
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._initialize_plugins())
            except RuntimeError:
                # No running loop yet (e.g. called from synchronous __init__)
                # Will be initialized lazily via ensure_initialized()
                logger.info("No running event loop — plugins will init on first use")
        else:
            self._init_done = True
            logger.info("PluginHardwareGateway: mode=mock (plugins not initialized)")

    def _load_hardware_schema(self) -> None:
        """Load unified plugin config from YAML (connection + peripherals)."""
        try:
            default_config_path = Path(__file__).parent / "hardware_config.yaml"
            if default_config_path.exists():
                loaded = PluginRegistry.load_configs_from_yaml(default_config_path)
                self._plugin_configs.update(loaded)
                logger.info(
                    "Loaded unified plugin config from %s (%d plugins)",
                    default_config_path,
                    len(loaded),
                )
            else:
                logger.warning(f"Hardware config file not found: {default_config_path}")
        except Exception as exc:
            logger.warning(f"Failed to load hardware config: {exc}")

    def _load_plugin_configs(self, config_source: Any) -> None:
        """Load plugin configurations from settings or config file."""
        # If configs were already loaded from YAML in _load_hardware_schema, skip
        if self._plugin_configs:
            logger.info("Plugin configs already loaded from YAML, skipping env fallback")
            return

        # Try to load from explicit config file path
        if isinstance(config_source, (str, Path)):
            config_path = Path(config_source)
            if config_path.exists():
                try:
                    loaded = PluginRegistry.load_configs_from_yaml(config_path)
                    self._plugin_configs.update(loaded)
                    return
                except Exception as exc:
                    logger.warning(f"Failed to load plugin config from {config_path}: {exc}")

        # Fallback to environment-based configuration
        self._create_default_configs()

    def _create_default_configs(self) -> None:
        """Create default plugin configurations from environment variables."""
        settings = get_settings()

        self._plugin_configs["piadc"] = PluginConfig(
            plugin_id="piadc",
            enabled=True,
            connection_type="http",
            connection_params={"base_url": settings.piadc_url},
            timeout=5.0,
            retry_count=3,
        )

        self._plugin_configs["motor-dri0050"] = PluginConfig(
            plugin_id="motor-dri0050",
            enabled=True,
            connection_type="cli",
            connection_params={
                "command": "/home/tom/github/oqlos/venv/bin/dri0050-pwm",
                "port": "/dev/ttyUSB0",
            },
            timeout=5.0,
            retry_count=3,
        )

        self._plugin_configs["motor-tic249"] = PluginConfig(
            plugin_id="motor-tic249",
            enabled=True,
            connection_type="http",
            connection_params={"base_url": settings.lung_motor_url},
            timeout=5.0,
            retry_count=3,
        )

        self._plugin_configs["modbus-io"] = PluginConfig(
            plugin_id="modbus-io",
            enabled=True,
            connection_type="modbus-rtu",
            connection_params={
                "serial_port": settings.modbus_serial_port,
                "baudrate": settings.modbus_baud,
                "parity": settings.modbus_parity,
            },
            timeout=2.0,
            retry_count=3,
        )

    def _parse_plugin_configs(self, plugins_data: dict[str, dict[str, Any]]) -> None:
        """Parse plugin configurations from dictionary (Pydantic handles nesting)."""
        for plugin_id, config_data in plugins_data.items():
            self._plugin_configs[plugin_id] = PluginConfig(
                plugin_id=plugin_id,
                enabled=config_data.get("enabled", True),
                connection_type=config_data.get("connection_type", "http"),
                connection_params=config_data.get("connection_params", {}),
                timeout=config_data.get("timeout", 5.0),
                retry_count=config_data.get("retry_count", 3),
                metadata=config_data.get("metadata", {}),
                peripherals=config_data.get("peripherals", {}),
            )

    async def ensure_initialized(self) -> None:
        """Await this to guarantee all plugins are connected."""
        if not self._init_done and self.mode == "real":
            await self._initialize_plugins()

    async def _initialize_plugins(self) -> None:
        """Initialize all enabled plugins."""
        if self._init_done:
            return
        for plugin_id, config in self._plugin_configs.items():
            if not config.enabled:
                logger.info(f"Plugin {plugin_id} is disabled, skipping")
                continue

            try:
                instance = await PluginRegistry.create_instance(plugin_id, config)
                success = await instance.connect()
                if success:
                    self._plugins[plugin_id] = instance
                    logger.info(f"Plugin {plugin_id} initialized and connected")
                else:
                    logger.error(f"Failed to connect plugin {plugin_id}")
            except Exception as exc:
                logger.error(f"Failed to initialize plugin {plugin_id}: {exc}")
        self._init_done = True

    @property
    def is_real(self) -> bool:
        return self.mode == "real"

    async def set_valve(self, valve_id: str, value: bool) -> bool:
        """Set valve state using modbus plugin."""
        if not self.is_real:
            logger.info("[HW mock] SET_VALVE %s → %s", valve_id, value)
            return True

        plugin = self._plugins.get("modbus-io")
        if not plugin:
            logger.error("Modbus plugin not available")
            return False

        try:
            result = await plugin.execute_command("set_valve", {"valve_id": valve_id, "value": value})
            return result.get("success", False)
        except Exception as exc:
            logger.error("PluginHardwareGateway.set_valve error: %s", exc)
            return False

    async def set_pump(self, power_pct: float) -> dict[str, Any]:
        """Set pump power using motor plugin with detailed driver data."""
        if not self.is_real:
            logger.info("[HW mock] SET_PUMP %.1f%%", power_pct)
            return {"success": True, "data": {"power_pct": power_pct, "mock": True}}

        plugin = self._plugins.get("motor-dri0050")
        if not plugin:
            logger.error("Motor plugin not available")
            return {"success": False, "error": "Motor plugin not available"}

        try:
            result = await plugin.execute_command("set_speed", {"power_pct": power_pct})
            return result
        except Exception as exc:
            logger.error("PluginHardwareGateway.set_pump error: %s", exc)
            return {"success": False, "error": str(exc)}

    async def read_sensor(self, sensor_id: str) -> float | None:
        """Read sensor value using piadc plugin."""
        if not self.is_real:
            logger.info("[HW mock] READ_SENSOR %s → None", sensor_id)
            return None

        plugin = self._plugins.get("piadc")
        if not plugin:
            logger.error("PiADC plugin not available")
            return None

        try:
            result = await plugin.execute_command("read_sensor", {"sensor_id": sensor_id})
            if result.get("success"):
                return result.get("data")
            return None
        except Exception as exc:
            logger.error("PluginHardwareGateway.read_sensor error: %s", exc)
            return None

    async def set_lung(self, steps: int = 500, speed: int = 100000, cycles: int = 5, pause: float = 0.5) -> bool:
        """Start artificial lung reciprocating motion using lung plugin."""
        if not self.is_real:
            logger.info("[HW mock] SET_LUNG steps=%d speed=%d cycles=%d pause=%.1f", steps, speed, cycles, pause)
            return True

        plugin = self._plugins.get("motor-tic249")
        if not plugin:
            logger.error("Lung plugin not available")
            return False

        try:
            result = await plugin.execute_command("reciprocate", {
                "steps": steps,
                "speed": speed,
                "cycles": cycles,
                "pause": pause,
            })
            return result.get("success", False)
        except Exception as exc:
            logger.error("PluginHardwareGateway.set_lung error: %s", exc)
            return False

    async def stop_lung(self) -> bool:
        """Emergency stop the artificial lung motor using lung plugin."""
        if not self.is_real:
            logger.info("[HW mock] STOP_LUNG")
            return True

        plugin = self._plugins.get("motor-tic249")
        if not plugin:
            logger.error("Lung plugin not available")
            return False

        try:
            result = await plugin.execute_command("stop", {})
            return result.get("success", False)
        except Exception as exc:
            logger.error("PluginHardwareGateway.stop_lung error: %s", exc)
            return False

    async def reload_configs(self, config_path: str | None = None) -> dict[str, Any]:
        """
        Hot-reload plugin configurations from YAML.

        Updates peripheral definitions (scales, conversions, units) on
        already-connected plugin instances without reconnecting.

        Returns summary of changes applied.
        """
        path = Path(config_path) if config_path else (
            Path(__file__).parent / "hardware_config.yaml"
        )
        try:
            new_configs = PluginRegistry.load_configs_from_yaml(path)
        except Exception as exc:
            logger.error("reload_configs failed: %s", exc)
            return {"success": False, "error": str(exc)}

        updated: list[str] = []
        for plugin_id, new_cfg in new_configs.items():
            self._plugin_configs[plugin_id] = new_cfg
            instance = self._plugins.get(plugin_id)
            if instance:
                instance.config = new_cfg
                updated.append(plugin_id)
                logger.info("Hot-reloaded config for %s (%d peripherals)",
                            plugin_id, len(new_cfg.peripherals))

        return {
            "success": True,
            "reloaded": len(new_configs),
            "updated_instances": updated,
        }

    async def health(self) -> dict[str, Any]:
        """Return health status of all plugins."""
        result = {"mode": self.mode}
        if not self.is_real:
            result["note"] = "mock mode — no hardware calls"
            return result

        health_results = await PluginRegistry.health_check_all()
        for plugin_id, health in health_results.items():
            result[plugin_id] = {
                "status": health.status.value,
                "message": health.message,
                "compatible": health.compatible,
            }

        return result
