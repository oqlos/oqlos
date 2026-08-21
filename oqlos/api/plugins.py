"""
REST API for hardware plugin management.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from oqlos.errors import OqlosError
from oqlos.errors.c2004_catalog_generated import CATALOG, c2004_code_for_issue
from oqlos.errors.catalog import ISSUE_CATALOG
from oqlos.hardware.power_safety import command_power_policy, ensure_power_safe

from oqlos.hardware.plugins import (
    PluginConfig,
    PluginHealth,
    PluginStatus,
    PluginRegistry,
    PiadcPlugin,
    ModbusAdcPlugin,
    MotorPlugin,
    ModbusPlugin,
    M54In8OutPlugin,
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
    PluginRegistry.register(M54In8OutPlugin)
    PluginRegistry.register(LungPlugin)
    PluginRegistry.discover_entry_point_plugins()
    _PLUGINS_INITIALIZED = True


router = APIRouter(prefix="/api/v1/plugins", tags=["plugins"])

_HEALTH_HTTP_OK = frozenset(
    {PluginStatus.CONNECTED.value, PluginStatus.CONFIGURED.value}
)

_PLUGIN_ISSUE_BY_ID = {
    "modbus-adc": "hw_usb_adc_sidecar_unreachable",
    "motor-dri0050": "hw_dri0050_sidecar_unreachable",
    "motor-tic249": "hw_tic249_sidecar_unreachable",
    "artificial-lung": "hw_tic249_sidecar_unreachable",
    "piadc": "hw_usb_adc_sidecar_unreachable",
    "io-m5-4in8out": "hw_m5_4in8out_no_response",
}

_PLUGIN_TARGET_BY_ID = {
    plugin_id: f"hardware-plugin://{plugin_id}"
    for plugin_id in {
        "artificial-lung",
        "io-m5-4in8out",
        "modbus-adc",
        "modbus-io",
        "motor-dri0050",
        "motor-tic249",
        "piadc",
    }
}


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


_PLUGIN_REQUEST_VALIDATION_MARKERS = (
    "valve_id is required",
    "unknown valve_id",
    "coil is required",
    "coil must be",
    "must be a non-negative integer",
    "unknown command",
)


def _resolve_execute_params(command: dict[str, Any]) -> dict[str, Any]:
    """Accept both ``params`` and legacy ``args`` bodies for plugin execute."""
    from oqlos.api.command_kwargs import resolve_args_or_params

    return resolve_args_or_params(command, prefer="params")


def _plugin_health_issue_code(
    plugin_id: str, body: dict[str, Any] | None = None
) -> str:
    """Map plugin health failures to operator issue codes.

    ``modbus-io`` uses ``hw_modbus_no_response`` for bus/timeout failures so HUI
    and plugin health share the same repair hint. Request/argument validation
    failures must stay ``api_diagnostic_command_invalid`` — otherwise a missing
    ``valve_id`` (often from ``args`` vs ``params``) is misdiagnosed as RS485.
    Prefer an explicit ``issue_code`` from the plugin command result when present
    so command-rejected failures are not always remapped to ``*_sidecar_unreachable``.
    """
    normalized = str(plugin_id or "").strip().lower()
    body = body or {}
    explicit = str(body.get("issue_code") or "").strip()
    if explicit and explicit in ISSUE_CATALOG:
        return explicit
    # Some plugins put the issue code only under nested upstream Problem Details.
    upstream = body.get("upstream") if isinstance(body.get("upstream"), dict) else {}
    nested = str(upstream.get("issue_code") or "").strip()
    if nested and nested in ISSUE_CATALOG:
        return nested
    message = str(body.get("message") or body.get("error") or "").lower()
    if any(marker in message for marker in _PLUGIN_REQUEST_VALIDATION_MARKERS):
        return "api_diagnostic_command_invalid"
    if normalized == "modbus-io":
        return "hw_modbus_no_response"
    if normalized == "modbus-adc" and any(
        marker in message
        for marker in ("timed out", "timeout", "no response", "did not answer")
    ):
        return "hw_modbus_no_response"
    return _PLUGIN_ISSUE_BY_ID.get(
        normalized, "adapter_configured-plugin_health_not_ok"
    )


def _raise_unhealthy_plugin(
    plugin_id: str,
    body: dict[str, Any] | None = None,
    *,
    stage: str = "plugin.health",
    operation_id: str = "plugin.health",
    reason: str = "plugin-unavailable",
    public_code: str | None = None,
    cause: BaseException | None = None,
) -> None:
    issue_code = _plugin_health_issue_code(plugin_id, body)
    resolved_public_code = (
        public_code if public_code in CATALOG else c2004_code_for_issue(issue_code)
    )
    entry = CATALOG[resolved_public_code]
    safe_plugin_id = str(plugin_id or "").strip()
    detail: dict[str, Any] = {
        "architecture": "SOA",
        "layer": "firmware",
        "component": "plugin-registry",
        "stage": stage,
        "problem_source": "hardware",
        "operation_id": operation_id,
        "upstream_target": _PLUGIN_TARGET_BY_ID.get(
            safe_plugin_id.lower(),
            "hardware-plugin://configured-plugin",
        ),
        "reason": reason,
        "issue_code": issue_code,
    }
    if safe_plugin_id:
        detail["peripheral_id"] = safe_plugin_id
    error = OqlosError(
        code=issue_code,
        public_code=resolved_public_code,
        status_code=entry.http_status,
        message=entry.message,
        detail=detail,
    )
    if cause is not None:
        raise error from cause
    raise error


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
        raise OqlosError(
            code="api_plugin_not_found",
            status_code=404,
            detail={
                "architecture": "SOA",
                "layer": "firmware",
                "component": "plugin-registry",
                "stage": "plugin.lookup",
                "problem_source": "request",
                "operation_id": "plugin.get",
            },
        )
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
        _raise_unhealthy_plugin(
            plugin_id,
            body,
            stage="plugin.health",
            operation_id="plugin.health",
            reason="instance-unavailable",
        )
    body = _plugin_health_body(health)
    if _plugin_health_http_status(health) != 200:
        _raise_unhealthy_plugin(
            plugin_id,
            body,
            stage="plugin.health",
            operation_id="plugin.health",
            reason="health-not-ok",
        )
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
        # Keep the gateway fast-path consistent with the process-wide registry.
        # HUI readiness intentionally avoids reconnecting dead hardware, so a
        # plugin connected through this management endpoint must be attached
        # explicitly or the GUI will continue to report it as unavailable.
        from oqlos.api.hardware_gateway import try_get_hardware_gateway

        gateway = try_get_hardware_gateway()
        instance = PluginRegistry.get_instance(plugin_id)
        if gateway is not None and instance is not None:
            gateway._plugins[plugin_id] = instance
        return {"status": "connected", "plugin_id": plugin_id}
    else:
        _raise_unhealthy_plugin(
            plugin_id,
            {
                "status": "error",
                "message": f"Failed to connect to plugin '{plugin_id}'",
                "compatible": False,
            },
            stage="plugin.connect",
            operation_id="plugin.connect",
            reason="connect-failed",
        )


@router.post("/{plugin_id}/disconnect")
async def disconnect_plugin(plugin_id: str):
    """Disconnect from a hardware plugin."""
    success = await PluginRegistry.disconnect_plugin(plugin_id)
    if success:
        from oqlos.api.hardware_gateway import try_get_hardware_gateway

        gateway = try_get_hardware_gateway()
        if gateway is not None:
            gateway._plugins.pop(plugin_id, None)
        return {"status": "disconnected", "plugin_id": plugin_id}
    else:
        _raise_unhealthy_plugin(
            plugin_id,
            {
                "status": "error",
                "message": f"Failed to disconnect from plugin '{plugin_id}'",
                "compatible": False,
            },
            stage="plugin.disconnect",
            operation_id="plugin.disconnect",
            reason="disconnect-failed",
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
    except (OSError, RuntimeError):
        return None


@router.post("/{plugin_id}/execute")
async def execute_plugin_command(plugin_id: str, command: dict[str, Any]):
    """Execute a command on a hardware plugin."""
    command_name = command.get("command")
    params = _resolve_execute_params(command)
    from oqlos.api.hardware_gateway import try_get_hardware_gateway

    gateway = try_get_hardware_gateway()
    if gateway is not None:
        policy = command_power_policy(command_name, params)
        await ensure_power_safe(
            gateway,
            operation=f"plugin:{plugin_id}.{command_name}",
            safe_state=policy != "actuation",
        )

    instance = await _resolve_plugin_instance(plugin_id)
    if not instance:
        _raise_unhealthy_plugin(
            plugin_id,
            {
                "status": "error",
                "message": f"No active instance for plugin '{plugin_id}'",
                "compatible": False,
            },
            stage="plugin.instance.resolve",
            operation_id="plugin.execute",
            reason="instance-unavailable",
        )

    result = await instance.execute_command(command_name, params)
    if isinstance(result, dict):
        if result.get("success") is False:
            _raise_unhealthy_plugin(
                plugin_id,
                result,
                stage="plugin.command.execute",
                operation_id="plugin.execute",
                reason="command-rejected",
                public_code=str(result.get("error_code") or ""),
            )
        return result
    _raise_unhealthy_plugin(
        plugin_id,
        stage="plugin.command.execute",
        operation_id="plugin.execute",
        reason="invalid-plugin-response",
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
