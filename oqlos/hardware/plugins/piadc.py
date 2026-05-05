"""
PiADC plugin - ADS1115 16-bit ADC sensor integration.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .base import HardwarePlugin, PluginConfig, PluginHealth, PluginStatus
from ._shared import http_health_check, not_connected_health, health_check_exception, http_disconnect

logger = logging.getLogger(__name__)


class PiadcPlugin(HardwarePlugin):
    """
    Plugin for piADC (ADS1115) 16-bit ADC sensor.

    Configuration:
        connection_type: "http"
        connection_params:
            base_url: e.g., "http://localhost:8080"
    """

    PLUGIN_ID = "piadc"
    PLUGIN_NAME = "piADC ADS1115"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_DESCRIPTION = "ADS1115 16-bit ADC — 4-channel analog input sensor"
    REQUIRED_PYTHON_PACKAGES = ["httpx"]
    SUPPORTED_PROTOCOLS = ["http", "i2c"]

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
        self._base_url = self.config.connection_params.get("base_url", "http://localhost:8080").rstrip("/")

    def validate_config(self) -> list[str]:
        """Validate piADC-specific configuration."""
        errors = []
        if self.config.connection_type != "http":
            errors.append("piadc currently only supports HTTP connection type")

        base_url = self.config.connection_params.get("base_url")
        if not base_url:
            errors.append("base_url is required in connection_params")
        elif not base_url.startswith(("http://", "https://")):
            errors.append("base_url must start with http:// or https://")

        return errors

    async def connect(self) -> bool:
        """Connect to piADC service."""
        try:
            self._client = httpx.AsyncClient(timeout=self.config.timeout)
            # Test connection with health check
            resp = await self._client.get(f"{self._base_url}/health")
            if resp.status_code < 300:
                self._status = PluginStatus.CONNECTED
                logger.info(f"Connected to piADC at {self._base_url}")
                return True
            else:
                self._status = PluginStatus.ERROR
                logger.error(f"piADC health check failed: HTTP {resp.status_code}")
                return False
        except Exception as exc:
            self._status = PluginStatus.ERROR
            logger.error(f"Failed to connect to piADC: {exc}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from piADC service."""
        await http_disconnect(self._client, "piADC")
        self._client = None
        self._status = PluginStatus.CONFIGURED

    async def health_check(self) -> PluginHealth:
        """Check piADC health and compatibility."""
        if not self._client:
            return not_connected_health("piADC")

        try:
            health = await http_health_check(self._client, self._base_url, "piADC")
            details = health.details if isinstance(health.details, dict) else {}
            if details.get("mock_mode") is True:
                return PluginHealth(
                    status=PluginStatus.ERROR,
                    message="piADC service is in mock_mode; real ADC readings are not available",
                    details=details,
                    compatible=False,
                    version=health.version,
                )
            if details.get("initialized") is False:
                return PluginHealth(
                    status=PluginStatus.ERROR,
                    message="piADC service is not initialized",
                    details=details,
                    compatible=False,
                    version=health.version,
                )
            return health
        except Exception as exc:
            return health_check_exception(exc)

    async def execute_command(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute piADC command."""
        if not self._client:
            return {"success": False, "error": "Not connected to piADC"}

        try:
            if command == "read_channel":
                channel = params.get("channel", 0)
                resp = await self._client.get(f"{self._base_url}/read/{channel}")
                if resp.status_code < 300:
                    return {"success": True, "data": resp.json()}
                else:
                    return {"success": False, "error": f"HTTP {resp.status_code}"}
            elif command == "read_sensor":
                sensor_id = params.get("sensor_id")
                if not sensor_id:
                    return {"success": False, "error": "sensor_id is required"}
                # Map sensor IDs to channels
                channel_map = {
                    "nc-sensor": 0,
                    "sc-sensor": 1,
                    "wc-sensor": 2,
                }
                channel = channel_map.get(sensor_id)
                if channel is None:
                    return {"success": False, "error": f"Unknown sensor_id: {sensor_id}"}
                resp = await self._client.get(f"{self._base_url}/read/{channel}")
                if resp.status_code < 300:
                    data = resp.json()
                    return {"success": True, "data": data.get("voltage")}
                else:
                    return {"success": False, "error": f"HTTP {resp.status_code}"}
            else:
                return {"success": False, "error": f"Unknown command: {command}"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @classmethod
    def get_capabilities(cls) -> dict[str, Any]:
        """Return piADC plugin capabilities."""
        capabilities = super().get_capabilities()
        capabilities.update({
            "supported_commands": ["read_channel", "read_sensor"],
            "supported_sensors": ["nc-sensor", "sc-sensor", "wc-sensor"],
            "channels": {
                "0": "NC sensor (mbar)",
                "1": "SC sensor (bar)",
                "2": "WC sensor (bar)",
                "3": "spare",
            },
            "configuration_schema": {
                "connection_type": {"type": "string", "enum": ["http"], "default": "http"},
                "connection_params": {
                    "type": "object",
                    "properties": {
                        "base_url": {"type": "string", "format": "uri"},
                    },
                    "required": ["base_url"],
                },
            },
        })
        return capabilities
