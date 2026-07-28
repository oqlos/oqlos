"""
REST API for hardware plugin management.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from oqlos.errors import OqlosError

from oqlos.hardware.plugins import (
    PluginConfig,
    PluginHealth,
    PluginStatus,
    PluginRegistry,
    PiadcPlugin,
    ModbusAdcPlugin,
    MotorPlugin,
    ModbusPlugin,
    LungPlugin,
)

_PLUGINS_INITIALIZED = False


def ensure_plugins_initialized() -> None:
    """Register and discover plugins once per process."""
    global _PLUGINS_INITIALIZED
    if _PLUGINS_INITIALIZED:
        return

    PluginRegistry.register(PiadcPlugin)
    PluginRegistry.register(ModbusAdcPlugin)
    PluginRegistry.register(MotorPlugin)
    PluginRegistry.register(ModbusPlugin)
    PluginRegistry.register(LungPlugin)
    PluginRegistry.discover_entry_point_plugins()
    _PLUGINS_INITIALIZED = True


router = APIRouter(prefix="/api/v1/plugins", tags=["plugins"])

_HEALTH_HTTP_OK = frozenset(
    {PluginStatus.CONNECTED.value, PluginStatus.CONFIGURED.value}
)


def _plugin_health_http_status(health: PluginHealth) -> int:
    """Map plugin health to HTTP status — errors must not masquerade as 200 OK."""
    return 200 if health.status.value in _HEALTH_HTTP_OK else 503


def _plugin_health_body(health: PluginHealth) -> dict[str, Any]:
    return {
        "status": health.status.value,
        "message": health.message,
        "compatible": health.compatible,
        "version": health.version,
        "details": health.details,
    }


def _plugin_health_issue_code(
    plugin_id: str, body: dict[str, Any] | None = None
) -> str:
    normalized = str(plugin_id or "unknown").strip().lower() or "unknown"
    message = str((body or {}).get("message") or "").lower()
    if normalized in {"modbus-io", "modbus-adc"} and any(
        marker in message
        for marker in ("timed out", "timeout", "no response", "did not answer")
    ):
        return "hw_modbus_no_response"
    return f"adapter_{normalized}_health_not_ok"


def _raise_unhealthy_plugin(plugin_id: str, body: dict[str, Any]) -> None:
    message = str(body.get("message") or f"Plugin '{plugin_id}' is unavailable")
    raise OqlosError(
        code=_plugin_health_issue_code(plugin_id, body),
        status_code=503,
        message=message,
        detail={"plugin_id": plugin_id, "health": body},
    )


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
        body = {
            "status": PluginStatus.ERROR.value,
            "message": f"No active instance for plugin '{plugin_id}'",
            "compatible": False,
            "version": "unknown",
            "details": {},
        }
        _raise_unhealthy_plugin(plugin_id, body)
    body = _plugin_health_body(health)
    if _plugin_health_http_status(health) != 200:
        _raise_unhealthy_plugin(plugin_id, body)
    return JSONResponse(content=body, status_code=200)


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
        peripherals=config.get("peripherals", {}),
    )

    success = await PluginRegistry.connect_plugin(plugin_id, plugin_config)
    if success:
        return {"status": "connected", "plugin_id": plugin_id}
    else:
        _raise_unhealthy_plugin(
            plugin_id,
            {
                "status": "error",
                "message": f"Failed to connect to plugin '{plugin_id}'",
                "compatible": False,
            },
        )


@router.post("/{plugin_id}/disconnect")
async def disconnect_plugin(plugin_id: str):
    """Disconnect from a hardware plugin."""
    success = await PluginRegistry.disconnect_plugin(plugin_id)
    if success:
        return {"status": "disconnected", "plugin_id": plugin_id}
    else:
        _raise_unhealthy_plugin(
            plugin_id,
            {
                "status": "error",
                "message": f"Failed to disconnect from plugin '{plugin_id}'",
                "compatible": False,
            },
        )


async def _resolve_plugin_instance(plugin_id: str) -> Any | None:
    """Return a connected plugin instance, creating one on demand when needed."""
    instance = PluginRegistry.get_instance(plugin_id)
    if instance is not None:
        return instance
    try:
        from oqlos.api.hardware import _gw

        gateway = _gw()
        await gateway.ensure_initialized()
        return await gateway._get_or_connect_plugin(plugin_id)
    except Exception:
        return None


@router.post("/{plugin_id}/execute")
async def execute_plugin_command(plugin_id: str, command: dict[str, Any]):
    """Execute a command on a hardware plugin."""
    instance = await _resolve_plugin_instance(plugin_id)
    if not instance:
        _raise_unhealthy_plugin(
            plugin_id,
            {
                "status": "error",
                "message": f"No active instance for plugin '{plugin_id}'",
                "compatible": False,
            },
        )

    command_name = command.get("command")
    params = command.get("params", {})

    result = await instance.execute_command(command_name, params)
    if isinstance(result, dict):
        if result.get("success") is False:
            status_code = int(result.get("status_code") or result.get("status") or 503)
            headers = {}
            if result.get("correlation_id"):
                headers["X-Correlation-ID"] = str(result["correlation_id"])
            media_type = "application/problem+json" if result.get("error_code") else "application/json"
            return JSONResponse(
                content=result,
                status_code=status_code,
                headers=headers,
                media_type=media_type,
            )
        return result
    raise OqlosError(
        code=f"adapter_{plugin_id}_health_not_ok",
        status_code=503,
        message="Invalid plugin response",
        detail={"plugin_id": plugin_id, "result_type": type(result).__name__},
    )


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
            peripherals=config_data.get("peripherals", {}),
        )

    errors = PluginRegistry.validate_all_configurations(plugin_configs)
    if errors:
        return {"valid": False, "errors": errors}
    else:
        return {"valid": True, "errors": {}}
