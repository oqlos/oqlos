"""
Hardware plugin registry - manages plugin discovery, registration, and lifecycle.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Type

import yaml

from .base import (
    HardwarePlugin,
    OqlosConfigDocument,
    PluginConfig,
    PluginHealth,
    PluginStatus,
    get_pluggy_manager,
)

logger = logging.getLogger(__name__)


class PluginRegistry:
    """
    Central registry for hardware plugins.

    Manages:
    - Plugin discovery and registration
    - Plugin lifecycle (connect, disconnect, health checks)
    - Plugin configuration validation
    - Error reporting and diagnostics
    """

    _plugins: dict[str, Type[HardwarePlugin]] = {}
    _instances: dict[str, HardwarePlugin] = {}

    @classmethod
    def register(cls, plugin_class: Type[HardwarePlugin]) -> Type[HardwarePlugin]:
        """
        Register a hardware plugin class.

        Usage:
            @PluginRegistry.register()
            class PiadcPlugin(HardwarePlugin):
                ...
        """
        plugin_id = plugin_class.PLUGIN_ID
        if plugin_id in cls._plugins:
            logger.warning(f"Plugin {plugin_id} already registered, overwriting")

        cls._plugins[plugin_id] = plugin_class
        logger.info(f"Registered plugin: {plugin_id} ({plugin_class.PLUGIN_NAME})")
        return plugin_class

    @classmethod
    def unregister(cls, plugin_id: str) -> bool:
        """Unregister a plugin by ID."""
        if plugin_id in cls._plugins:
            del cls._plugins[plugin_id]
            if plugin_id in cls._instances:
                del cls._instances[plugin_id]
            logger.info(f"Unregistered plugin: {plugin_id}")
            return True
        return False

    @classmethod
    def get_plugin_class(cls, plugin_id: str) -> Type[HardwarePlugin] | None:
        """Get a plugin class by ID."""
        return cls._plugins.get(plugin_id)

    @classmethod
    def list_plugins(cls) -> list[dict[str, Any]]:
        """List all registered plugins with their metadata."""
        return [
            {
                "plugin_id": plugin_id,
                "name": plugin_class.PLUGIN_NAME,
                "version": plugin_class.PLUGIN_VERSION,
                "description": plugin_class.PLUGIN_DESCRIPTION,
                "required_packages": plugin_class.REQUIRED_PYTHON_PACKAGES,
                "supported_protocols": plugin_class.SUPPORTED_PROTOCOLS,
            }
            for plugin_id, plugin_class in cls._plugins.items()
        ]

    @classmethod
    async def create_instance(cls, plugin_id: str, config: PluginConfig) -> HardwarePlugin:
        """
        Create and initialize a plugin instance.

        Raises:
            ValueError: If plugin is not registered
            RuntimeError: If configuration is invalid
        """
        plugin_class = cls.get_plugin_class(plugin_id)
        if not plugin_class:
            raise ValueError(f"Plugin {plugin_id} is not registered")

        # Validate configuration
        config_errors = config.validate()
        if config_errors:
            raise RuntimeError(f"Invalid configuration: {', '.join(config_errors)}")

        # Create instance
        instance = plugin_class(config)

        # Validate plugin-specific configuration
        plugin_errors = instance.validate_config()
        if plugin_errors:
            raise RuntimeError(f"Plugin validation failed: {', '.join(plugin_errors)}")

        cls._instances[plugin_id] = instance
        logger.info(f"Created instance of plugin: {plugin_id}")
        return instance

    @classmethod
    def get_instance(cls, plugin_id: str) -> HardwarePlugin | None:
        """Get an existing plugin instance by ID."""
        return cls._instances.get(plugin_id)

    @classmethod
    async def connect_plugin(cls, plugin_id: str, config: PluginConfig) -> bool:
        """
        Create and connect a plugin instance.

        Returns True if connection successful, False otherwise.
        """
        try:
            instance = await cls.create_instance(plugin_id, config)
            success = await instance.connect()
            if success:
                instance._status = PluginStatus.CONNECTED
            else:
                instance._status = PluginStatus.ERROR
            return success
        except Exception as exc:
            logger.error(f"Failed to connect plugin {plugin_id}: {exc}")
            return False

    @classmethod
    async def disconnect_plugin(cls, plugin_id: str) -> bool:
        """Disconnect and remove a plugin instance."""
        instance = cls.get_instance(plugin_id)
        if instance:
            try:
                await instance.disconnect()
                instance._status = PluginStatus.CONFIGURED
                del cls._instances[plugin_id]
                logger.info(f"Disconnected plugin: {plugin_id}")
                return True
            except Exception as exc:
                logger.error(f"Failed to disconnect plugin {plugin_id}: {exc}")
                return False
        return False

    @classmethod
    async def health_check(cls, plugin_id: str) -> PluginHealth | None:
        """Perform health check on a plugin instance."""
        instance = cls.get_instance(plugin_id)
        if instance:
            try:
                health = await instance.health_check()
                instance._health = health
                instance._status = health.status
                return health
            except Exception as exc:
                logger.error(f"Health check failed for plugin {plugin_id}: {exc}")
                return PluginHealth(
                    status=PluginStatus.ERROR,
                    message=f"Health check exception: {exc}",
                    compatible=False,
                )
        return None

    @classmethod
    async def health_check_all(cls) -> dict[str, PluginHealth]:
        """Perform health checks on all active plugin instances."""
        results = {}
        for plugin_id in cls._instances:
            health = await cls.health_check(plugin_id)
            if health:
                results[plugin_id] = health
        return results

    @classmethod
    def validate_all_configurations(cls, configs: dict[str, PluginConfig]) -> dict[str, list[str]]:
        """
        Validate configurations for multiple plugins.

        Returns a dictionary mapping plugin IDs to lists of error messages.
        """
        errors: dict[str, list[str]] = {}
        for plugin_id, config in configs.items():
            plugin_class = cls.get_plugin_class(plugin_id)
            if not plugin_class:
                errors[plugin_id] = [f"Plugin {plugin_id} is not registered"]
                continue

            # Validate base configuration
            config_errors = config.validate()
            if config_errors:
                errors[plugin_id] = config_errors
                continue

            # Validate plugin-specific configuration
            temp_instance = plugin_class(config)
            plugin_errors = temp_instance.validate_config()
            if plugin_errors:
                errors[plugin_id] = plugin_errors

        return errors

    @classmethod
    def get_status(cls) -> dict[str, Any]:
        """Get overall status of all plugins."""
        return {
            "registered_plugins": len(cls._plugins),
            "active_instances": len(cls._instances),
            "plugins": [
                {
                    "plugin_id": plugin_id,
                    "status": instance.status.value,
                    "connected": instance.is_connected,
                }
                for plugin_id, instance in cls._instances.items()
            ],
        }

    # ------------------------------------------------------------------
    # Entry-point discovery (stevedore-like, stdlib only)
    # ------------------------------------------------------------------

    @classmethod
    def discover_entry_point_plugins(
        cls, group: str = "oqlos_hardware"
    ) -> list[str]:
        """
        Discover and register plugins from installed entry points.

        Third-party packages expose plugins via::

            [project.entry-points."oqlos_hardware"]
            my_driver = "my_package:MyDriverPlugin"

        If the loaded object has ``PLUGIN_ID`` it is registered as an
        ABC-based plugin.  Otherwise it is registered with the pluggy
        PluginManager for hookspec-based drivers.

        Returns list of discovered plugin IDs / entry-point names.
        """
        from importlib.metadata import entry_points

        discovered: list[str] = []
        eps = entry_points(group=group)
        for ep in eps:
            try:
                plugin_obj = ep.load()
                if (
                    isinstance(plugin_obj, type)
                    and issubclass(plugin_obj, HardwarePlugin)
                    and hasattr(plugin_obj, "PLUGIN_ID")
                ):
                    cls.register(plugin_obj)
                    discovered.append(plugin_obj.PLUGIN_ID)
                else:
                    # Hookspec-based driver — register with pluggy PM
                    pm = get_pluggy_manager()
                    pm.register(plugin_obj, name=ep.name)
                    discovered.append(ep.name)
                logger.info("Discovered entry-point plugin: %s", ep.name)
            except Exception as exc:
                logger.error("Failed to load entry point %s: %s", ep.name, exc)
        return discovered

    # ------------------------------------------------------------------
    # YAML configuration reload
    # ------------------------------------------------------------------

    @classmethod
    def load_configs_from_yaml(
        cls, config_path: str | Path
    ) -> dict[str, PluginConfig]:
        """
        Load (or reload) plugin configurations from a unified YAML file.

        The YAML format is::

            plugins:
              motor-dri0050:
                enabled: true
                connection_type: http
                connection_params:
                  base_url: http://localhost:49055
                peripherals:
                  speed:
                    name: speed
                    type: pump
                    scale: {min: 0, max: 100, unit: "l/min"}
                    conversion: {type: linear, scale: 0.1}

        Returns dict mapping plugin_id -> PluginConfig.
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path) as fh:
            data = yaml.safe_load(fh) or {}

        document = OqlosConfigDocument.model_validate(data)
        configs: dict[str, PluginConfig] = {}
        for plugin_id, plugin_config in document.plugins.items():
            configs[plugin_id] = plugin_config.model_copy(update={"plugin_id": plugin_id})
            logger.info("Loaded config for plugin: %s", plugin_id)
        return configs
