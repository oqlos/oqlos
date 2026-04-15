"""
REST API for hardware plugin management.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from oqlos.hardware.plugins import (
    PluginConfig,
    PluginHealth,
    PluginRegistry,
    PiadcPlugin,
    MotorPlugin,
    ModbusPlugin,
    LungPlugin,
)

# Register built-in plugins
PluginRegistry.register(PiadcPlugin)
PluginRegistry.register(MotorPlugin)
PluginRegistry.register(ModbusPlugin)
PluginRegistry.register(LungPlugin)

router = APIRouter(prefix="/api/v1/plugins", tags=["plugins"])


@router.get("/")
async def list_plugins():
    """List all registered hardware plugins."""
    return {"plugins": PluginRegistry.list_plugins()}


@router.get("/status")
async def get_plugin_status():
    """Get overall status of all plugins."""
    return PluginRegistry.get_status()


@router.get("/{plugin_id}")
async def get_plugin_info(plugin_id: str):
    """Get information about a specific plugin."""
    plugin_class = PluginRegistry.get_plugin_class(plugin_id)
    if not plugin_class:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    return plugin_class.get_capabilities()


@router.get("/{plugin_id}/health")
async def get_plugin_health(plugin_id: str):
    """Get health status of a specific plugin."""
    health = await PluginRegistry.health_check(plugin_id)
    if not health:
        raise HTTPException(status_code=404, detail=f"No active instance for plugin '{plugin_id}'")
    return {
        "status": health.status.value,
        "message": health.message,
        "compatible": health.compatible,
        "version": health.version,
        "details": health.details,
    }


@router.post("/{plugin_id}/connect")
async def connect_plugin(plugin_id: str, config: dict[str, Any]):
    """Connect to a hardware plugin."""
    plugin_config = PluginConfig(
        plugin_id=plugin_id,
        enabled=config.get("enabled", True),
        connection_type=config.get("connection_type", "http"),
        connection_params=config.get("connection_params", {}),
        timeout=config.get("timeout", 5.0),
        retry_count=config.get("retry_count", 3),
        metadata=config.get("metadata", {}),
    )

    success = await PluginRegistry.connect_plugin(plugin_id, plugin_config)
    if success:
        return {"status": "connected", "plugin_id": plugin_id}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to connect to plugin '{plugin_id}'")


@router.post("/{plugin_id}/disconnect")
async def disconnect_plugin(plugin_id: str):
    """Disconnect from a hardware plugin."""
    success = await PluginRegistry.disconnect_plugin(plugin_id)
    if success:
        return {"status": "disconnected", "plugin_id": plugin_id}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to disconnect from plugin '{plugin_id}'")


@router.post("/{plugin_id}/execute")
async def execute_plugin_command(plugin_id: str, command: dict[str, Any]):
    """Execute a command on a hardware plugin."""
    instance = PluginRegistry.get_instance(plugin_id)
    if not instance:
        raise HTTPException(status_code=404, detail=f"No active instance for plugin '{plugin_id}'")

    command_name = command.get("command")
    params = command.get("params", {})

    result = await instance.execute_command(command_name, params)
    if result.get("success"):
        return result
    else:
        raise HTTPException(status_code=500, detail=result.get("error", "Command failed"))


@router.post("/validate")
async def validate_plugin_configs(configs: dict[str, dict[str, Any]]):
    """Validate configurations for multiple plugins."""
    plugin_configs = {}
    for plugin_id, config_data in configs.items():
        plugin_configs[plugin_id] = PluginConfig(
            plugin_id=plugin_id,
            enabled=config_data.get("enabled", True),
            connection_type=config_data.get("connection_type", "http"),
            connection_params=config_data.get("connection_params", {}),
            timeout=config_data.get("timeout", 5.0),
            retry_count=config_data.get("retry_count", 3),
            metadata=config_data.get("metadata", {}),
        )

    errors = PluginRegistry.validate_all_configurations(plugin_configs)
    if errors:
        return {"valid": False, "errors": errors}
    else:
        return {"valid": True, "errors": {}}
