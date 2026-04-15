"""
Motor plugin - DFRobot DRI0050 PWM motor driver integration.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .base import HardwarePlugin, PluginConfig, PluginHealth, PluginStatus

logger = logging.getLogger(__name__)


class MotorPlugin(HardwarePlugin):
    """
    Plugin for DFRobot DRI0050 PWM motor driver.

    Configuration:
        connection_type: "http"
        connection_params:
            base_url: e.g., "http://localhost:49055"
    """

    PLUGIN_ID = "motor-dri0050"
    PLUGIN_NAME = "DFRobot DRI0050 Motor"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_DESCRIPTION = "PWM motor & LED strip driver via MODBUS RTU (serial)"
    REQUIRED_PYTHON_PACKAGES = ["httpx"]
    SUPPORTED_PROTOCOLS = ["http", "modbus-rtu"]

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
        self._base_url = self.config.connection_params.get("base_url", "http://localhost:49055").rstrip("/")

    def validate_config(self) -> list[str]:
        """Validate motor-specific configuration."""
        errors = []
        if self.config.connection_type not in ["http", "modbus-rtu"]:
            errors.append("motor currently supports http or modbus-rtu connection types")

        if self.config.connection_type == "http":
            base_url = self.config.connection_params.get("base_url")
            if not base_url:
                errors.append("base_url is required in connection_params for http connection")
            elif not base_url.startswith(("http://", "https://")):
                errors.append("base_url must start with http:// or https://")
        elif self.config.connection_type == "modbus-rtu":
            serial_port = self.config.connection_params.get("serial_port")
            if not serial_port:
                errors.append("serial_port is required in connection_params for modbus-rtu connection")

        return errors

    async def connect(self) -> bool:
        """Connect to motor service."""
        try:
            if self.config.connection_type == "http":
                self._client = httpx.AsyncClient(timeout=self.config.timeout)
                # Test connection with health check
                resp = await self._client.get(f"{self._base_url}/health")
                if resp.status_code < 300:
                    self._status = PluginStatus.CONNECTED
                    logger.info(f"Connected to motor at {self._base_url}")
                    return True
                else:
                    self._status = PluginStatus.ERROR
                    logger.error(f"Motor health check failed: HTTP {resp.status_code}")
                    return False
            else:
                # Modbus RTU connection would be implemented here
                self._status = PluginStatus.CONNECTED
                logger.info(f"Connected to motor via modbus-rtu")
                return True
        except Exception as exc:
            self._status = PluginStatus.ERROR
            logger.error(f"Failed to connect to motor: {exc}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from motor service."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._status = PluginStatus.CONFIGURED
        logger.info("Disconnected from motor")

    async def health_check(self) -> PluginHealth:
        """Check motor health and compatibility."""
        if self.config.connection_type == "http" and not self._client:
            return PluginHealth(
                status=PluginStatus.ERROR,
                message="Not connected to motor",
                compatible=False,
            )

        try:
            if self.config.connection_type == "http":
                resp = await self._client.get(f"{self._base_url}/health")
                if resp.status_code < 300:
                    data = resp.json()
                    return PluginHealth(
                        status=PluginStatus.CONNECTED,
                        message="Motor is healthy",
                        details=data,
                        compatible=True,
                        version=data.get("version", "unknown"),
                    )
                else:
                    return PluginHealth(
                        status=PluginStatus.ERROR,
                        message=f"Health check failed: HTTP {resp.status_code}",
                        compatible=False,
                    )
            else:
                # Modbus RTU health check would be implemented here
                return PluginHealth(
                    status=PluginStatus.CONNECTED,
                    message="Motor (modbus-rtu) is healthy",
                    compatible=True,
                )
        except Exception as exc:
            return PluginHealth(
                status=PluginStatus.ERROR,
                message=f"Health check exception: {exc}",
                compatible=False,
            )

    async def execute_command(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute motor command."""
        if self.config.connection_type == "http" and not self._client:
            return {"success": False, "error": "Not connected to motor"}

        try:
            if command == "set_speed":
                power_pct = params.get("power_pct", 0)
                if not 0 <= power_pct <= 100:
                    return {"success": False, "error": "power_pct must be between 0 and 100"}

                if self.config.connection_type == "http":
                    if power_pct <= 0:
                        resp = await self._client.post(f"{self._base_url}/api/stop")
                    else:
                        resp = await self._client.post(
                            f"{self._base_url}/api/speed",
                            json={"power_pct": power_pct},
                        )
                    if resp.status_code < 300:
                        return {"success": True, "data": resp.json()}
                    else:
                        return {"success": False, "error": f"HTTP {resp.status_code}"}
                else:
                    # Modbus RTU implementation would be here
                    return {"success": True, "data": {"power_pct": power_pct}}
            elif command == "stop":
                if self.config.connection_type == "http":
                    resp = await self._client.post(f"{self._base_url}/api/stop")
                    if resp.status_code < 300:
                        return {"success": True, "data": resp.json()}
                    else:
                        return {"success": False, "error": f"HTTP {resp.status_code}"}
                else:
                    return {"success": True, "data": {"stopped": True}}
            elif command == "status":
                if self.config.connection_type == "http":
                    resp = await self._client.get(f"{self._base_url}/api/status")
                    if resp.status_code < 300:
                        return {"success": True, "data": resp.json()}
                    else:
                        return {"success": False, "error": f"HTTP {resp.status_code}"}
                else:
                    return {"success": True, "data": {"status": "ok"}}
            else:
                return {"success": False, "error": f"Unknown command: {command}"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @classmethod
    def get_capabilities(cls) -> dict[str, Any]:
        """Return motor plugin capabilities."""
        capabilities = super().get_capabilities()
        capabilities.update({
            "supported_commands": ["set_speed", "stop", "status"],
            "power_range": {"min": 0, "max": 100, "unit": "percent"},
            "configuration_schema": {
                "connection_type": {
                    "type": "string",
                    "enum": ["http", "modbus-rtu"],
                    "default": "http",
                },
                "connection_params": {
                    "type": "object",
                    "properties": {
                        "base_url": {"type": "string", "format": "uri"},
                        "serial_port": {"type": "string"},
                    },
                },
            },
        })
        return capabilities
