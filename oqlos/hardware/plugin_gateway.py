"""
Plugin-based Hardware Gateway - simplified architecture using hardware plugins.

This replaces the old HardwareGateway with hardcoded adapters by using the
new plugin system. All hardware communication goes through standardized plugins
with validated configuration and clear error reporting.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from oqlos.config import get_settings
from oqlos.hardware.config_paths import resolve_oqlos_config_path
from oqlos.hardware.plugins import (
    PluginConfig,
    PluginRegistry,
    PiadcPlugin,
    ModbusAdcPlugin,
    MotorPlugin,
    ModbusPlugin,
    LungPlugin,
)
from oqlos.hardware.tic249_units import TIC249_DEFAULT_TARGET_VELOCITY

logger = logging.getLogger(__name__)

# Register built-in plugins
PluginRegistry.register(PiadcPlugin)
PluginRegistry.register(ModbusAdcPlugin)
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
        self._init_lock = asyncio.Lock()
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
            self._apply_env_overrides()
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
        self._apply_env_overrides()

    def _apply_env_overrides(self) -> None:
        """Let deployment env point YAML-defined plugins at host/external services."""
        url_overrides = {
            "piadc": ("OQLOS_PIADC_URL", "PIADC_URL"),
            "motor-dri0050": ("OQLOS_MOTOR_URL", "MOTOR_URL"),
            "motor-tic249": ("OQLOS_LUNG_MOTOR_URL", "LUNG_MOTOR_URL"),
        }
        for plugin_id, env_names in url_overrides.items():
            value = next((os.getenv(name) for name in env_names if os.getenv(name)), None)
            if not value or plugin_id not in self._plugin_configs:
                continue
            self._plugin_configs[plugin_id].connection_params["base_url"] = value.rstrip("/")
            logger.info("Hardware plugin %s base_url overridden by env", plugin_id)

        self._apply_shared_modbus_bus_env_overrides()
        self._apply_modbus_env_overrides(
            "modbus-io",
            {
                "serial_port": ("OQLOS_MODBUS_SERIAL_PORT", "MODBUS_SERIAL_PORT"),
                "baudrate": ("OQLOS_MODBUS_BAUD", "MODBUS_BAUD", "MODBUS_BAUD_RATE"),
                "parity": ("OQLOS_MODBUS_PARITY", "MODBUS_PARITY"),
                "device_id": ("OQLOS_MODBUS_DEVICE_ID", "MODBUS_DEVICE_ID"),
            },
        )
        self._apply_modbus_env_overrides(
            "modbus-adc",
            {
                "serial_port": ("OQLOS_MODBUS_ADC_SERIAL_PORT", "MODBUS_ADC_SERIAL_PORT"),
                "baudrate": ("OQLOS_MODBUS_ADC_BAUD", "MODBUS_ADC_BAUD", "MODBUS_ADC_BAUD_RATE"),
                "parity": ("OQLOS_MODBUS_ADC_PARITY", "MODBUS_ADC_PARITY"),
                "device_id": ("OQLOS_MODBUS_ADC_DEVICE_ID", "MODBUS_ADC_DEVICE_ID"),
                "read_address": ("OQLOS_MODBUS_ADC_READ_ADDRESS", "MODBUS_ADC_READ_ADDRESS"),
                "read_count": ("OQLOS_MODBUS_ADC_READ_COUNT", "MODBUS_ADC_READ_COUNT"),
            },
        )
        self._log_modbus_preflight()

    def _apply_shared_modbus_bus_env_overrides(self) -> None:
        """Apply one-bus RS485 aliases before per-plugin overrides."""
        shared_serial = next((
            os.getenv(name)
            for name in (
                "OQLOS_MODBUS_BUS_SERIAL_PORT",
                "MODBUS_BUS_SERIAL_PORT",
                "OQLOS_MODBUS_SHARED_SERIAL_PORT",
                "MODBUS_SHARED_SERIAL_PORT",
            )
            if os.getenv(name)
        ), None)
        shared_baud = next((
            os.getenv(name)
            for name in ("OQLOS_MODBUS_BUS_BAUD", "MODBUS_BUS_BAUD", "MODBUS_SHARED_BAUD")
            if os.getenv(name)
        ), None)
        shared_parity = next((
            os.getenv(name)
            for name in ("OQLOS_MODBUS_BUS_PARITY", "MODBUS_BUS_PARITY", "MODBUS_SHARED_PARITY")
            if os.getenv(name)
        ), None)

        for plugin_id in ("modbus-io", "modbus-adc"):
            plugin_config = self._plugin_configs.get(plugin_id)
            if plugin_config is None:
                continue
            if shared_serial:
                plugin_config.connection_params["serial_port"] = shared_serial
            if shared_baud:
                try:
                    plugin_config.connection_params["baudrate"] = int(shared_baud)
                except ValueError:
                    logger.warning("Ignoring invalid shared Modbus baud override: %s", shared_baud)
            if shared_parity:
                plugin_config.connection_params["parity"] = shared_parity.upper()

    def _apply_modbus_env_overrides(
        self,
        plugin_id: str,
        overrides: dict[str, tuple[str, ...]],
    ) -> None:
        plugin_config = self._plugin_configs.get(plugin_id)
        if plugin_config is None:
            return

        for param_name, env_names in overrides.items():
            value = next((os.getenv(name) for name in env_names if os.getenv(name)), None)
            if value is None:
                continue
            if param_name in {"baudrate", "device_id", "read_address", "read_count"}:
                try:
                    plugin_config.connection_params[param_name] = int(value)
                except ValueError:
                    logger.warning("Ignoring invalid %s %s override: %s", plugin_id, param_name, value)
            else:
                plugin_config.connection_params[param_name] = value

    def modbus_preflight_report(self) -> dict[str, Any]:
        """Validate Modbus RTU topology with the shared pimodbus rules."""
        try:
            from pimodbus.config import validate_plugin_configs
        except ImportError as exc:
            return {
                "ok": False,
                "topology": "unknown",
                "modules": [],
                "issues": [
                    {
                        "severity": "error",
                        "code": "pimodbus_unavailable",
                        "message": f"pimodbus library is not available: {exc}",
                        "modules": ["modbus-io", "modbus-adc"],
                        "repair": {"install": "/home/tom/github/maskservice/pimodbus"},
                    }
                ],
                "recommended": {},
            }

        configs: dict[str, Any] = {}
        for plugin_id, config in self._plugin_configs.items():
            if plugin_id in {"modbus-io", "modbus-adc"}:
                configs[plugin_id] = config.model_dump(mode="python")
        return validate_plugin_configs(configs).to_dict()

    def _log_modbus_preflight(self) -> None:
        report = self.modbus_preflight_report()
        for issue in report.get("issues", []):
            message = issue.get("message", "")
            if issue.get("severity") == "error":
                logger.error("Modbus preflight: %s", message)
            else:
                logger.warning("Modbus preflight: %s", message)

    async def ensure_initialized(self) -> None:
        """Await this to guarantee all plugins are connected."""
        if not self._init_done and self.mode == "real":
            await self._initialize_plugins()

    async def _get_or_connect_plugin(self, plugin_id: str) -> Any | None:
        """Return a connected plugin, retrying plugins that were unavailable at startup."""
        await self.ensure_initialized()

        plugin = self._plugins.get(plugin_id)
        if plugin:
            return plugin

        instance = PluginRegistry.get_instance(plugin_id)
        if instance:
            try:
                health = await instance.health_check()
                if health.compatible:
                    self._plugins[plugin_id] = instance
                    logger.info("Plugin %s recovered after startup and is now connected", plugin_id)
                    return instance
            except Exception as exc:
                logger.debug("Health check before reconnect failed for plugin %s: %s", plugin_id, exc)

        config = self._plugin_configs.get(plugin_id)
        if not config or not config.enabled:
            return None

        try:
            if instance is None:
                instance = await PluginRegistry.create_instance(plugin_id, config)
            success = await instance.connect()
        except Exception as exc:
            logger.error("Failed to reconnect plugin %s: %s", plugin_id, exc)
            return None

        if success:
            self._plugins[plugin_id] = instance
            logger.info("Plugin %s reconnected on demand", plugin_id)
            return instance

        return None

    async def _initialize_plugins(self) -> None:
        """Initialize all enabled plugins in parallel."""
        if self._init_done:
            return

        async with self._init_lock:
            if self._init_done:
                return

            async def _connect_one(plugin_id: str, config: PluginConfig) -> None:
                if not config.enabled:
                    logger.info(f"Plugin {plugin_id} is disabled, skipping")
                    return
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

            await asyncio.gather(*[
                _connect_one(pid, cfg)
                for pid, cfg in self._plugin_configs.items()
            ])
            self._init_done = True

    @property
    def is_real(self) -> bool:
        return self.mode == "real"

    async def set_valve(self, valve_id: str, value: bool) -> bool:
        """Set valve state using modbus plugin."""
        if not self.is_real:
            logger.info("[HW mock] SET_VALVE %s → %s", valve_id, value)
            return True

        plugin = await self._get_or_connect_plugin("modbus-io")
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

        plugin = await self._get_or_connect_plugin("motor-dri0050")
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
        """Read sensor value using the Modbus ADC plugin."""
        if not self.is_real:
            logger.info("[HW mock] READ_SENSOR %s → None", sensor_id)
            return None

        plugin = await self._get_or_connect_plugin("modbus-adc")
        if not plugin:
            logger.error("Modbus ADC plugin not available")
            return None

        try:
            result = await plugin.execute_command("read_sensor", {"sensor_id": sensor_id})
            if result.get("success"):
                return result.get("data")
            return None
        except Exception as exc:
            logger.error("PluginHardwareGateway.read_sensor error: %s", exc)
            return None

    async def set_lung_result(
        self,
        steps: int = 500,
        speed: int = TIC249_DEFAULT_TARGET_VELOCITY,
        cycles: int = 5,
        pause: float = 0.5,
    ) -> dict[str, Any]:
        """Start artificial lung reciprocating motion and return detailed plugin result."""
        if not self.is_real:
            logger.info("[HW mock] SET_LUNG steps=%d speed=%d cycles=%d pause=%.1f", steps, speed, cycles, pause)
            return {
                "success": True,
                "data": {
                    "steps": steps,
                    "speed": speed,
                    "cycles": cycles,
                    "pause": pause,
                    "mock": True,
                },
            }

        await self.ensure_initialized()
        plugin = self._plugins.get("motor-tic249")
        if not plugin:
            logger.error("Lung plugin not available")
            return {"success": False, "error": "Lung plugin not available"}

        try:
            result = await plugin.execute_command("reciprocate", {
                "steps": steps,
                "speed": speed,
                "cycles": cycles,
                "pause": pause,
            })
            return result if isinstance(result, dict) else {"success": False, "error": "Invalid plugin response"}
        except Exception as exc:
            logger.error("PluginHardwareGateway.set_lung error: %s", exc)
            return {"success": False, "error": str(exc)}

    async def set_lung(self, steps: int = 500, speed: int = TIC249_DEFAULT_TARGET_VELOCITY, cycles: int = 5, pause: float = 0.5) -> bool:
        """Compatibility bool API for scenario executor paths."""
        result = await self.set_lung_result(steps=steps, speed=speed, cycles=cycles, pause=pause)
        return bool(result.get("success", False))

    async def stop_lung(self) -> bool:
        """Emergency stop the artificial lung motor using lung plugin."""
        if not self.is_real:
            logger.info("[HW mock] STOP_LUNG")
            return True

        await self.ensure_initialized()
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

    async def disable_lung(self) -> bool:
        """De-energize the artificial lung motor (release coils) using lung plugin."""
        if not self.is_real:
            logger.info("[HW mock] DISABLE_LUNG")
            return True

        await self.ensure_initialized()
        plugin = self._plugins.get("motor-tic249")
        if not plugin:
            logger.error("Lung plugin not available")
            return False

        try:
            result = await plugin.execute_command("energize", {"enable": False})
            return result.get("success", False)
        except Exception as exc:
            logger.error("PluginHardwareGateway.disable_lung error: %s", exc)
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

        health_results = await PluginRegistry.health_check_all(timeout=2.5)
        for plugin_id, health in health_results.items():
            result[plugin_id] = {
                "status": health.status.value,
                "message": health.message,
                "compatible": health.compatible,
            }

        return result
