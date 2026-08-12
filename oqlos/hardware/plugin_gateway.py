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
from oqlos.hardware.plugin_gateway_boundary import (
    CONFIGURATION_ERRORS,
    PLUGIN_OPERATION_ERRORS,
    configuration_failure as _configuration_failure,
    log_boundary_failure as _log_boundary_failure,
    normalize_plugin_command_result as _normalize_plugin_command_result,
    plugin_command_failure as _plugin_command_failure,
)
from oqlos.hardware.plugins import (
    PluginConfig,
    PluginHealth,
    PluginRegistry,
    PiadcPlugin,
    ModbusAdcPlugin,
    MotorPlugin,
    ModbusPlugin,
    LungPlugin,
)
from oqlos.hardware.power_safety import ensure_power_safe
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
        self._motor2_runtime: dict[str, Any] = {}

        self._init_done = False
        self._init_lock = asyncio.Lock()
        self._reconfigure_lock = asyncio.Lock()
        self._suspended_plugins: set[str] = set()
        self._runtime_loop: asyncio.AbstractEventLoop | None = None
        self.last_init_summary: dict[str, Any] = {}
        if self.mode == "real":
            self._load_hardware_schema(config_path)
            logger.info(
                "PluginHardwareGateway ready (real); plugins connect on ensure_initialized()"
            )
        else:
            self._init_done = True
            logger.info("PluginHardwareGateway: mode=mock (plugins not initialized)")

    def _load_hardware_schema(self, config_path: str | None = None) -> None:
        """Load unified plugin config from YAML (connection + peripherals)."""
        try:
            selected_path = resolve_oqlos_config_path(config_path)
            from oqlos.hardware.configuration import load_hardware_configuration

            document = load_hardware_configuration(selected_path, allow_legacy=True)
            motor2 = document.runtime.get("motor2")
            self._motor2_runtime = dict(motor2) if isinstance(motor2, dict) else {}
            loaded = PluginRegistry.load_configs(selected_path)
            self._plugin_configs.update(loaded)
            self._apply_env_overrides()
            self._apply_persisted_modbus_settings()
            self._log_modbus_preflight()
            logger.info(
                "Loaded unified hardware configuration from %s (%d plugins)",
                selected_path,
                len(loaded),
            )
            if not loaded:
                raise RuntimeError(f"No plugins defined in config: {selected_path}")
        except CONFIGURATION_ERRORS as exc:
            _log_boundary_failure(logger, "Hardware configuration load failed", exc)
            raise RuntimeError("Failed to load OqlOS hardware configuration") from None

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
            value = next(
                (os.getenv(name) for name in env_names if os.getenv(name)), None
            )
            if not value or plugin_id not in self._plugin_configs:
                continue
            self._plugin_configs[plugin_id].connection_params["base_url"] = (
                value.rstrip("/")
            )
            logger.info("Hardware plugin %s base_url overridden by env", plugin_id)

        self._apply_plugin_enable_env_overrides()
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
                "serial_port": (
                    "OQLOS_MODBUS_ADC_SERIAL_PORT",
                    "MODBUS_ADC_SERIAL_PORT",
                ),
                "baudrate": (
                    "OQLOS_MODBUS_ADC_BAUD",
                    "MODBUS_ADC_BAUD",
                    "MODBUS_ADC_BAUD_RATE",
                ),
                "parity": ("OQLOS_MODBUS_ADC_PARITY", "MODBUS_ADC_PARITY"),
                "device_id": ("OQLOS_MODBUS_ADC_DEVICE_ID", "MODBUS_ADC_DEVICE_ID"),
                "read_address": (
                    "OQLOS_MODBUS_ADC_READ_ADDRESS",
                    "MODBUS_ADC_READ_ADDRESS",
                ),
                "read_count": ("OQLOS_MODBUS_ADC_READ_COUNT", "MODBUS_ADC_READ_COUNT"),
            },
        )

    def _apply_persisted_modbus_settings(self) -> dict[str, dict[str, Any]]:
        """Make the operator profile authoritative for live Modbus plugins."""
        from oqlos.api.hardware_modbus_settings import apply_modbus_runtime_settings

        applied = apply_modbus_runtime_settings(get_settings(), self._plugin_configs)
        for plugin_id, values in applied.items():
            logger.info(
                "Applied Modbus runtime profile to %s: port=%s baud=%s parity=%s device_id=%s",
                plugin_id,
                values.get("serial_port"),
                values.get("baudrate"),
                values.get("parity"),
                values.get("device_id"),
            )
        return applied

    async def apply_modbus_user_settings(
        self,
        plugin_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        """Apply persisted settings immediately and reconnect RTU plugins without actuation."""
        await self.ensure_initialized()
        async with self._reconfigure_lock:
            applied = self._apply_persisted_modbus_settings()
            reconnects: list[dict[str, Any]] = []
            for plugin_id in ("modbus-io", "modbus-adc"):
                if plugin_ids is not None and plugin_id not in plugin_ids:
                    continue
                config = self._plugin_configs.get(plugin_id)
                if config is None or not config.enabled or plugin_id not in applied:
                    continue
                self._plugins.pop(plugin_id, None)
                await PluginRegistry.disconnect_plugin(plugin_id)
                ok = await PluginRegistry.connect_plugin(plugin_id, config)
                instance = PluginRegistry.get_instance(plugin_id)
                if ok and instance is not None:
                    self._plugins[plugin_id] = instance
                reconnects.append({"plugin_id": plugin_id, "ok": bool(ok)})
            return {
                "ok": all(item["ok"] for item in reconnects),
                "applied": applied,
                "reconnects": reconnects,
                "actuation": False,
            }

    async def suspend_plugins(self, plugin_ids: set[str]) -> set[str]:
        """Temporarily prevent on-demand reconnect while a service tool owns a port."""
        await self.ensure_initialized()
        selected = {
            plugin_id
            for plugin_id in plugin_ids
            if plugin_id in self._plugin_configs
            and self._plugin_configs[plugin_id].enabled
        }
        if not selected:
            return set()
        async with self._reconfigure_lock:
            self._suspended_plugins.update(selected)
            for plugin_id in selected:
                self._plugins.pop(plugin_id, None)
                await PluginRegistry.disconnect_plugin(plugin_id)
        return selected

    async def resume_modbus_plugins(self, plugin_ids: set[str]) -> dict[str, Any]:
        """Reconnect suspended RTU plugins from persisted settings, without actuation."""
        await self.ensure_initialized()
        selected = set(plugin_ids)
        async with self._reconfigure_lock:
            applied = self._apply_persisted_modbus_settings()
            reconnects: list[dict[str, Any]] = []
            try:
                for plugin_id in selected:
                    config = self._plugin_configs.get(plugin_id)
                    if config is None or not config.enabled or plugin_id not in applied:
                        continue
                    self._plugins.pop(plugin_id, None)
                    await PluginRegistry.disconnect_plugin(plugin_id)
                    ok = await PluginRegistry.connect_plugin(plugin_id, config)
                    instance = PluginRegistry.get_instance(plugin_id)
                    if ok and instance is not None:
                        self._plugins[plugin_id] = instance
                    reconnects.append({"plugin_id": plugin_id, "ok": bool(ok)})
            finally:
                self._suspended_plugins.difference_update(selected)
            return {
                "ok": all(item["ok"] for item in reconnects),
                "applied": applied,
                "reconnects": reconnects,
                "actuation": False,
            }

    def _apply_plugin_enable_env_overrides(self) -> None:
        """Disable optional plugins on benches (motors/piadc) to avoid extra serial/USB churn."""
        allow_csv = next(
            (
                os.getenv(name)
                for name in ("OQLOS_HARDWARE_PLUGINS", "C2004_HARDWARE_PLUGINS")
                if os.getenv(name)
            ),
            None,
        )
        disable_csv = next(
            (
                os.getenv(name)
                for name in ("OQLOS_DISABLE_PLUGINS", "C2004_HARDWARE_DISABLE_PLUGINS")
                if os.getenv(name)
            ),
            None,
        )

        if allow_csv:
            allowed = {part.strip() for part in allow_csv.split(",") if part.strip()}
            for plugin_id, plugin_config in self._plugin_configs.items():
                plugin_config.enabled = plugin_id in allowed
            logger.info("Hardware plugins allow-list from env: %s", sorted(allowed))
            return

        if not disable_csv:
            return

        disabled = {part.strip() for part in disable_csv.split(",") if part.strip()}
        for plugin_id in disabled:
            plugin_config = self._plugin_configs.get(plugin_id)
            if plugin_config is None:
                continue
            plugin_config.enabled = False
            logger.info("Hardware plugin %s disabled via env", plugin_id)

    def _apply_shared_modbus_bus_env_overrides(self) -> None:
        """Apply one-bus RS485 aliases before per-plugin overrides."""
        shared_serial = next(
            (
                os.getenv(name)
                for name in (
                    "OQLOS_MODBUS_BUS_SERIAL_PORT",
                    "MODBUS_BUS_SERIAL_PORT",
                    "OQLOS_MODBUS_SHARED_SERIAL_PORT",
                    "MODBUS_SHARED_SERIAL_PORT",
                )
                if os.getenv(name)
            ),
            None,
        )
        shared_baud = next(
            (
                os.getenv(name)
                for name in (
                    "OQLOS_MODBUS_BUS_BAUD",
                    "MODBUS_BUS_BAUD",
                    "MODBUS_SHARED_BAUD",
                )
                if os.getenv(name)
            ),
            None,
        )
        shared_parity = next(
            (
                os.getenv(name)
                for name in (
                    "OQLOS_MODBUS_BUS_PARITY",
                    "MODBUS_BUS_PARITY",
                    "MODBUS_SHARED_PARITY",
                )
                if os.getenv(name)
            ),
            None,
        )

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
                    logger.warning(
                        "Ignoring invalid shared Modbus baud override: %s", shared_baud
                    )
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
            value = next(
                (os.getenv(name) for name in env_names if os.getenv(name)), None
            )
            if value is None:
                continue
            if param_name in {"baudrate", "device_id", "read_address", "read_count"}:
                try:
                    plugin_config.connection_params[param_name] = int(value)
                except ValueError:
                    logger.warning(
                        "Ignoring invalid %s %s override: %s",
                        plugin_id,
                        param_name,
                        value,
                    )
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
                        "repair": {"install": "/home/tom/github/oqlos/pimodbus"},
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
        self._runtime_loop = asyncio.get_running_loop()
        if not self._init_done and self.mode == "real":
            await self._initialize_plugins()

    async def _get_or_connect_plugin(self, plugin_id: str) -> Any | None:
        """Return a connected plugin, retrying plugins that were unavailable at startup."""
        await self.ensure_initialized()

        if plugin_id in self._suspended_plugins:
            logger.info("Plugin %s is temporarily suspended for service", plugin_id)
            return None

        plugin = self._plugins.get(plugin_id)
        if plugin:
            return plugin

        instance = PluginRegistry.get_instance(plugin_id)
        if instance:
            try:
                health = await instance.health_check()
                if health.compatible:
                    self._plugins[plugin_id] = instance
                    logger.info(
                        "Plugin %s recovered after startup and is now connected",
                        plugin_id,
                    )
                    return instance
            except PLUGIN_OPERATION_ERRORS as exc:
                _log_boundary_failure(
                    logger,
                    "Health check before reconnect failed for plugin %s",
                    exc,
                    plugin_id,
                    level=logging.DEBUG,
                )

        config = self._plugin_configs.get(plugin_id)
        if not config or not config.enabled:
            return None

        if plugin_id in self._suspended_plugins:
            return None

        try:
            if instance is None:
                instance = await PluginRegistry.create_instance(plugin_id, config)
            success = await instance.connect()
        except PLUGIN_OPERATION_ERRORS as exc:
            _log_boundary_failure(
                logger, "Failed to reconnect plugin %s", exc, plugin_id
            )
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

            summary: dict[str, Any] = {"connected": [], "failed": [], "disabled": []}

            async def _connect_one(plugin_id: str, config: PluginConfig) -> None:
                if not config.enabled:
                    logger.info("Plugin %s is disabled, skipping", plugin_id)
                    summary["disabled"].append(plugin_id)
                    return
                port_hint = ""
                if config.connection_type == "modbus-rtu":
                    port_hint = str(config.connection_params.get("serial_port") or "")
                elif config.connection_params.get("base_url"):
                    port_hint = str(config.connection_params.get("base_url"))
                try:
                    logger.info(
                        "Initializing plugin %s (%s)%s",
                        plugin_id,
                        config.connection_type,
                        f" port={port_hint}" if port_hint else "",
                    )
                    instance = await PluginRegistry.create_instance(plugin_id, config)
                    success = await instance.connect()
                    if success:
                        self._plugins[plugin_id] = instance
                        summary["connected"].append(plugin_id)
                        logger.info(
                            "Plugin %s connected%s",
                            plugin_id,
                            f" ({port_hint})" if port_hint else "",
                        )
                    else:
                        summary["failed"].append(
                            {"plugin_id": plugin_id, "reason": "connect returned false"}
                        )
                        logger.error(
                            "Plugin %s connect() returned false%s",
                            plugin_id,
                            f" ({port_hint})" if port_hint else "",
                        )
                except PLUGIN_OPERATION_ERRORS as exc:
                    summary["failed"].append(
                        {"plugin_id": plugin_id, "reason": "initialization-error"}
                    )
                    _log_boundary_failure(
                        logger, "Failed to initialize plugin %s", exc, plugin_id
                    )

            modbus_plugin_ids = ("modbus-io", "modbus-adc")
            other_plugins = [
                (pid, cfg)
                for pid, cfg in self._plugin_configs.items()
                if pid not in modbus_plugin_ids
            ]
            modbus_plugins = [
                (pid, self._plugin_configs[pid])
                for pid in modbus_plugin_ids
                if pid in self._plugin_configs
            ]

            if other_plugins:
                await asyncio.gather(
                    *[_connect_one(pid, cfg) for pid, cfg in other_plugins]
                )
            # Shared RS485 bus: connect Modbus plugins sequentially to avoid port races.
            for pid, cfg in modbus_plugins:
                if cfg.enabled:
                    await _connect_one(pid, cfg)
                else:
                    summary["disabled"].append(pid)
            self.last_init_summary = summary
            self._init_done = True
            if summary["failed"]:
                logger.warning(
                    "Hardware init finished with failures: connected=%s failed=%s disabled=%s",
                    summary["connected"],
                    summary["failed"],
                    summary["disabled"],
                )
            else:
                logger.info(
                    "Hardware init finished: connected=%s disabled=%s",
                    summary["connected"],
                    summary["disabled"],
                )

    @property
    def is_real(self) -> bool:
        return self.mode == "real"

    async def plugin_readiness(
        self,
        plugin_id: str,
        *,
        reconnect: bool = True,
    ) -> dict[str, Any]:
        """Expose HUI readiness, optionally without probing a disconnected device."""
        if not self.is_real:
            return {
                "ok": True,
                "plugin_id": plugin_id,
                "status": "mock",
                "message": "Hardware runtime is in mock mode",
            }

        config = self._plugin_configs.get(plugin_id)
        if config is None:
            return {
                "ok": False,
                "plugin_id": plugin_id,
                "status": "not_configured",
                "message": f"Plugin {plugin_id} is not configured",
            }
        if not config.enabled:
            return {
                "ok": False,
                "plugin_id": plugin_id,
                "status": "disabled",
                "message": f"Plugin {plugin_id} is disabled in OqlOS configuration",
            }

        if reconnect:
            plugin = await self._get_or_connect_plugin(plugin_id)
        else:
            await self.ensure_initialized()
            plugin = self._plugins.get(plugin_id)
        if plugin is None:
            return {
                "ok": False,
                "plugin_id": plugin_id,
                "status": "unavailable",
                "message": (
                    f"Plugin {plugin_id} could not connect"
                    if reconnect
                    else f"Plugin {plugin_id} is not connected"
                ),
            }

        try:
            health = await plugin.health_check()
        except PLUGIN_OPERATION_ERRORS as exc:
            _log_boundary_failure(
                logger,
                "Plugin readiness check failed plugin_id=%s",
                exc,
                plugin_id,
                level=logging.WARNING,
            )
            return {
                "ok": False,
                "plugin_id": plugin_id,
                "status": "error",
                "message": "Plugin health check failed",
            }

        compatible = bool(getattr(health, "compatible", False))
        health_status = getattr(health, "status", "ok" if compatible else "error")
        status = getattr(health_status, "value", health_status)
        return {
            "ok": compatible,
            "plugin_id": plugin_id,
            "status": str(status),
            "message": (
                "Plugin is ready" if compatible else "Plugin health is not compatible"
            ),
        }

    async def set_valve(self, valve_id: str, value: bool) -> bool:
        """Set valve state using modbus plugin."""
        if not self.is_real:
            logger.info("[HW mock] SET_VALVE %s → %s", valve_id, value)
            return True

        await ensure_power_safe(
            self,
            operation=f"modbus-io.set_valve:{valve_id}",
            safe_state=not value,
        )

        plugin = await self._get_or_connect_plugin("modbus-io")
        if not plugin:
            logger.error("Modbus plugin not available")
            return False

        try:
            result = await plugin.execute_command(
                "set_valve", {"valve_id": valve_id, "value": value}
            )
            return result.get("success", False)
        except PLUGIN_OPERATION_ERRORS as exc:
            _log_boundary_failure(
                logger, "PluginHardwareGateway.set_valve failed", exc
            )
            return False

    async def all_valves_off(self) -> dict[str, Any]:
        """Clear all Waveshare outputs in one Modbus transaction."""
        if not self.is_real:
            logger.info("[HW mock] ALL_VALVES_OFF")
            return {"success": True, "data": {"all_outputs": True, "mock": True}}

        await ensure_power_safe(
            self,
            operation="modbus-io.all_outputs_off",
            safe_state=True,
        )

        plugin = await self._get_or_connect_plugin("modbus-io")
        if not plugin:
            return _plugin_command_failure("plugin-unavailable")
        try:
            return _normalize_plugin_command_result(
                await plugin.execute_command("all_outputs_off", {})
            )
        except PLUGIN_OPERATION_ERRORS as exc:
            _log_boundary_failure(
                logger, "PluginHardwareGateway.all_valves_off failed", exc
            )
            return _plugin_command_failure("command-failed")

    async def set_pump(self, power_pct: float) -> dict[str, Any]:
        """Set pump power using motor plugin with detailed driver data."""
        if not self.is_real:
            logger.info("[HW mock] SET_PUMP %.1f%%", power_pct)
            return {"success": True, "data": {"power_pct": power_pct, "mock": True}}

        await ensure_power_safe(
            self,
            operation="motor-dri0050.set_pump",
            safe_state=power_pct <= 0,
        )

        plugin = await self._get_or_connect_plugin("motor-dri0050")
        if not plugin:
            logger.error("Motor plugin not available")
            return _plugin_command_failure("plugin-unavailable")

        try:
            result = await plugin.execute_command("set_speed", {"power_pct": power_pct})
            return _normalize_plugin_command_result(result)
        except PLUGIN_OPERATION_ERRORS as exc:
            _log_boundary_failure(
                logger, "PluginHardwareGateway.set_pump failed", exc
            )
            return _plugin_command_failure("command-failed")

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
            result = await plugin.execute_command(
                "read_sensor", {"sensor_id": sensor_id}
            )
            if result.get("success"):
                return result.get("data")
            return None
        except PLUGIN_OPERATION_ERRORS as exc:
            _log_boundary_failure(
                logger, "PluginHardwareGateway.read_sensor failed", exc
            )
            return None

    async def read_adc_channels(self) -> dict[str, Any] | None:
        """Read all Modbus ADC channels in one RTU transaction."""
        if not self.is_real:
            return None

        plugin = await self._get_or_connect_plugin("modbus-adc")
        if not plugin:
            return None

        try:
            result = await plugin.execute_command("read_all", {})
            if not result.get("success"):
                return None
            data = result.get("data") or {}
            channels = data.get("channels")
            return channels if isinstance(channels, dict) else None
        except PLUGIN_OPERATION_ERRORS as exc:
            _log_boundary_failure(
                logger, "PluginHardwareGateway.read_adc_channels failed", exc
            )
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
            logger.info(
                "[HW mock] SET_LUNG steps=%d speed=%d cycles=%d pause=%.1f",
                steps,
                speed,
                cycles,
                pause,
            )
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

        await ensure_power_safe(self, operation="motor-tic249.reciprocate")

        await self.ensure_initialized()
        plugin = self._plugins.get("motor-tic249")
        if not plugin:
            logger.error("Lung plugin not available")
            return _plugin_command_failure("plugin-unavailable")

        try:
            result = await plugin.execute_command(
                "reciprocate",
                {
                    "steps": steps,
                    "speed": speed,
                    "cycles": cycles,
                    "pause": pause,
                },
            )
            return _normalize_plugin_command_result(result)
        except PLUGIN_OPERATION_ERRORS as exc:
            _log_boundary_failure(
                logger, "PluginHardwareGateway.set_lung failed", exc
            )
            return _plugin_command_failure("command-failed")

    async def set_lung(
        self,
        steps: int = 500,
        speed: int = TIC249_DEFAULT_TARGET_VELOCITY,
        cycles: int = 5,
        pause: float = 0.5,
    ) -> bool:
        """Compatibility bool API for scenario executor paths."""
        result = await self.set_lung_result(
            steps=steps, speed=speed, cycles=cycles, pause=pause
        )
        return bool(result.get("success", False))

    async def _execute_lung_bool_command(
        self,
        command: str,
        params: dict[str, Any],
        *,
        mock_label: str,
        error_context: str,
    ) -> bool:
        if not self.is_real:
            logger.info("[HW mock] %s", mock_label)
            return True

        await self.ensure_initialized()
        plugin = self._plugins.get("motor-tic249")
        if not plugin:
            logger.error("Lung plugin not available")
            return False

        try:
            result = await plugin.execute_command(command, params)
            return result.get("success", False)
        except PLUGIN_OPERATION_ERRORS as exc:
            _log_boundary_failure(
                logger, "PluginHardwareGateway.%s failed", exc, error_context
            )
            return False

    async def stop_lung(self) -> bool:
        """Stop motion and release Tic249 coils according to the motor2 idle policy."""
        stop_params: dict[str, Any] = {}
        if self.motor2_stop_at_limit:
            stop_params["stop_mode"] = "reach_limit"
        stopped = await self._execute_lung_bool_command(
            "stop",
            stop_params,
            mock_label="STOP_LUNG",
            error_context="stop_lung",
        )
        if not self.motor2_deenergize_on_stop:
            return stopped
        if self.motor2_stop_at_limit:
            return stopped
        deenergized = await self.disable_lung()
        return stopped and deenergized

    async def disable_lung(self) -> bool:
        """De-energize the artificial lung motor (release coils) using lung plugin."""
        return await self._execute_lung_bool_command(
            "energize",
            {"enable": False},
            mock_label="DISABLE_LUNG",
            error_context="disable_lung",
        )

    @staticmethod
    def _runtime_bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return default

    @property
    def motor2_deenergize_on_stop(self) -> bool:
        idle_state = str(self._motor2_runtime.get("idleState") or "deenergized").strip().lower()
        return self._runtime_bool(
            self._motor2_runtime.get("deenergizeOnStop"),
            idle_state == "deenergized",
        )

    @property
    def motor2_deenergize_on_startup(self) -> bool:
        idle_state = str(self._motor2_runtime.get("idleState") or "deenergized").strip().lower()
        return self._runtime_bool(
            self._motor2_runtime.get("deenergizeOnStartup"),
            idle_state == "deenergized",
        )

    @property
    def motor2_stop_at_limit(self) -> bool:
        stop_mode = str(self._motor2_runtime.get("stopMode") or "").strip().lower()
        if "stopAtLimit" in self._motor2_runtime or "stop_at_limit" in self._motor2_runtime:
            return self._runtime_bool(self._motor2_runtime.get("stopAtLimit"), True)
        if stop_mode == "reach_limit":
            return True
        if stop_mode in {"immediate", "emergency"}:
            return False
        return True

    async def enforce_motor2_startup_idle_state(self) -> bool:
        """Release Tic249 coils at startup when configured for deenergized idle."""
        if not self.motor2_deenergize_on_startup:
            return True
        return await self.disable_lung()

    async def reload_configs(self, config_path: str | None = None) -> dict[str, Any]:
        """
        Hot-reload plugin configurations from YAML.

        Updates peripheral definitions (scales, conversions, units) on
        already-connected plugin instances without reconnecting.

        Returns summary of changes applied.
        """
        try:
            path = resolve_oqlos_config_path(config_path)
        except OSError:
            return _configuration_failure("config-path-unavailable")
        try:
            from oqlos.hardware.configuration import load_hardware_configuration

            document = load_hardware_configuration(path, allow_legacy=True)
            motor2 = document.runtime.get("motor2")
            self._motor2_runtime = dict(motor2) if isinstance(motor2, dict) else {}
            new_configs = PluginRegistry.load_configs(path)
        except CONFIGURATION_ERRORS as exc:
            _log_boundary_failure(logger, "Hardware configuration reload failed", exc)
            return _configuration_failure("config-load-failed")

        updated: list[str] = []
        for plugin_id, new_cfg in new_configs.items():
            self._plugin_configs[plugin_id] = new_cfg
            instance = self._plugins.get(plugin_id)
            if instance:
                instance.config = new_cfg
                updated.append(plugin_id)
                logger.info(
                    "Hot-reloaded config for %s (%d peripherals)",
                    plugin_id,
                    len(new_cfg.peripherals),
                )

        self._apply_env_overrides()
        self._apply_persisted_modbus_settings()
        self._log_modbus_preflight()

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

        await self.ensure_initialized()
        if self.last_init_summary:
            result["init_summary"] = self.last_init_summary

        # Must exceed plugin RTU timeout (typically 2s) + retries; 1.0s caused false
        # "Health check timed out" for healthy modbus-adc/io under parallel probes.
        _health_timeout = float(os.environ.get("OQLOS_PLUGIN_HEALTH_TIMEOUT", "6.0"))
        if self._plugin_configs:

            async def _check_enabled(plugin_id: str) -> tuple[str, PluginHealth | None]:
                health = await PluginRegistry.health_check(
                    plugin_id, timeout=_health_timeout
                )
                return plugin_id, health

            checks = [
                _check_enabled(plugin_id)
                for plugin_id, config in self._plugin_configs.items()
                if config.enabled
            ]
            health_results = dict(await asyncio.gather(*checks)) if checks else {}
        else:
            health_results = await PluginRegistry.health_check_all(
                timeout=_health_timeout
            )
        for plugin_id, health in health_results.items():
            if health is None:
                continue
            config = self._plugin_configs.get(plugin_id)
            result[plugin_id] = {
                "status": health.status.value,
                "message": (
                    "Plugin is healthy"
                    if health.compatible
                    else "Plugin health is unavailable"
                ),
                "compatible": health.compatible,
            }
            if config and config.metadata.get("required") is True:
                result[plugin_id]["required"] = True
        for plugin_id, config in self._plugin_configs.items():
            if plugin_id in result:
                continue
            if not config.enabled:
                result[plugin_id] = {
                    "status": "disabled",
                    "message": "Plugin is disabled in OqlOS configuration",
                    "compatible": False,
                }
            else:
                result[plugin_id] = {
                    "status": "error",
                    "message": "Plugin is configured but no active instance is connected",
                    "compatible": False,
                }
            if config.metadata.get("required") is True:
                result[plugin_id]["required"] = True

        return result
