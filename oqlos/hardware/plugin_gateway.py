"""
Plugin-based Hardware Gateway - simplified architecture using hardware plugins.

This replaces the old HardwareGateway with hardcoded adapters by using the
new plugin system. All hardware communication goes through standardized plugins
with validated configuration and clear error reporting.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from oqlos.config import get_settings
from oqlos.hardware.config_paths import resolve_oqlos_config_path
from oqlos.hardware.plugins import (
    PluginConfig,
    PluginRegistry,
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
            self._load_hardware_schema(config_path)
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

    def _load_hardware_schema(self, config_path: str | None = None) -> None:
        """Load unified plugin config from YAML (connection + peripherals)."""
        try:
            selected_path = resolve_oqlos_config_path(config_path)
            loaded = PluginRegistry.load_configs_from_yaml(selected_path)
            self._plugin_configs.update(loaded)
            logger.info(
                "Loaded unified plugin config from %s (%d plugins)",
                selected_path,
                len(loaded),
            )
            if not loaded:
                raise RuntimeError(f"No plugins defined in config: {selected_path}")
        except Exception as exc:
            raise RuntimeError(f"Failed to load oqlos.yaml configuration: {exc}") from exc

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
        try:
            path = resolve_oqlos_config_path(config_path)
        except Exception as exc:
            return {"success": False, "error": str(exc)}
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
