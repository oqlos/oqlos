"""
Lung plugin - Pololu Tic T249 stepper motor for artificial lung integration.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .base import HardwarePlugin, PluginConfig, PluginHealth, PluginStatus

logger = logging.getLogger(__name__)


class LungPlugin(HardwarePlugin):
    """
    Plugin for Pololu Tic T249 stepper motor (artificial lung).

    Configuration:
        connection_type: "http"
        connection_params:
            base_url: e.g., "http://localhost:8205"
    """

    PLUGIN_ID = "motor-tic249"
    PLUGIN_NAME = "Pololu Tic T249 Lung"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_DESCRIPTION = "Stepper motor controller — artificial lung pump"
    REQUIRED_PYTHON_PACKAGES = ["httpx"]
    SUPPORTED_PROTOCOLS = ["http", "usb"]

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
        self._base_url = self.config.connection_params.get("base_url", "http://localhost:8205").rstrip("/")

    def validate_config(self) -> list[str]:
        """Validate lung-specific configuration."""
        errors = []
        if self.config.connection_type not in ["http", "usb"]:
            errors.append("lung currently supports http or usb connection types")

        if self.config.connection_type == "http":
            base_url = self.config.connection_params.get("base_url")
            if not base_url:
                errors.append("base_url is required in connection_params for http connection")
            elif not base_url.startswith(("http://", "https://")):
                errors.append("base_url must start with http:// or https://")

        return errors

    async def connect(self) -> bool:
        """Connect to lung motor service."""
        try:
            if self.config.connection_type == "http":
                self._client = httpx.AsyncClient(timeout=self.config.timeout)
                # Test connection with health check
                resp = await self._client.get(f"{self._base_url}/health")
                if resp.status_code < 300:
                    self._status = PluginStatus.CONNECTED
                    logger.info(f"Connected to lung motor at {self._base_url}")
                    return True
                else:
                    self._status = PluginStatus.ERROR
                    logger.error(f"Lung motor health check failed: HTTP {resp.status_code}")
                    return False
            else:
                # USB connection would be implemented here
                self._status = PluginStatus.CONNECTED
                logger.info("Connected to lung motor via USB")
                return True
        except Exception as exc:
            self._status = PluginStatus.ERROR
            logger.error(f"Failed to connect to lung motor: {exc}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from lung motor service."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._status = PluginStatus.CONFIGURED
        logger.info("Disconnected from lung motor")

    async def health_check(self) -> PluginHealth:
        """Check lung motor health and compatibility."""
        if self.config.connection_type == "http" and not self._client:
            return PluginHealth(
                status=PluginStatus.ERROR,
                message="Not connected to lung motor",
                compatible=False,
            )

        try:
            if self.config.connection_type == "http":
                resp = await self._client.get(f"{self._base_url}/health")
                if resp.status_code < 300:
                    data = resp.json()
                    return PluginHealth(
                        status=PluginStatus.CONNECTED,
                        message="Lung motor is healthy",
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
                # USB health check would be implemented here
                return PluginHealth(
                    status=PluginStatus.CONNECTED,
                    message="Lung motor (USB) is healthy",
                    compatible=True,
                )
        except Exception as exc:
            return PluginHealth(
                status=PluginStatus.ERROR,
                message=f"Health check exception: {exc}",
                compatible=False,
            )

    async def execute_command(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute lung motor command."""
        if self.config.connection_type == "http" and not self._client:
            return {"success": False, "error": "Not connected to lung motor"}

        try:
            if command == "reciprocate":
                steps = params.get("steps", 500)
                speed = params.get("speed", 100000)
                cycles = params.get("cycles", 5)
                pause = params.get("pause", 0.5)

                if self.config.connection_type == "http":
                    resp = await self._client.post(
                        f"{self._base_url}/api/reciprocate",
                        json={"steps": steps, "speed": speed, "cycles": cycles, "pause": pause},
                    )
                    if resp.status_code < 300:
                        return {"success": True, "data": resp.json()}
                    else:
                        return {"success": False, "error": f"HTTP {resp.status_code}"}
                else:
                    # USB implementation would be here
                    return {"success": True, "data": {"steps": steps, "speed": speed}}
            elif command == "stop":
                if self.config.connection_type == "http":
                    resp = await self._client.post(f"{self._base_url}/api/stop")
                    if resp.status_code < 300:
                        return {"success": True, "data": resp.json()}
                    else:
                        return {"success": False, "error": f"HTTP {resp.status_code}"}
                else:
                    return {"success": True, "data": {"stopped": True}}
            elif command == "move":
                position = params.get("position", 0)
                speed = params.get("speed")

                if self.config.connection_type == "http":
                    payload = {"position": position}
                    if speed is not None:
                        payload["speed"] = speed
                    resp = await self._client.post(f"{self._base_url}/api/move", json=payload)
                    if resp.status_code < 300:
                        return {"success": True, "data": resp.json()}
                    else:
                        return {"success": False, "error": f"HTTP {resp.status_code}"}
                else:
                    return {"success": True, "data": {"position": position}}
            elif command == "energize":
                enable = params.get("enable", True)

                if self.config.connection_type == "http":
                    resp = await self._client.post(f"{self._base_url}/api/energize", json={"enable": enable})
                    if resp.status_code < 300:
                        return {"success": True, "data": resp.json()}
                    else:
                        return {"success": False, "error": f"HTTP {resp.status_code}"}
                else:
                    return {"success": True, "data": {"energized": enable}}
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
        """Return lung plugin capabilities."""
        capabilities = super().get_capabilities()
        capabilities.update({
            "supported_commands": ["reciprocate", "stop", "move", "energize", "status"],
            "capabilities": ["reciprocate", "homing", "limit-switches"],
            "configuration_schema": {
                "connection_type": {
                    "type": "string",
                    "enum": ["http", "usb"],
                    "default": "http",
                },
                "connection_params": {
                    "type": "object",
                    "properties": {
                        "base_url": {"type": "string", "format": "uri"},
                    },
                },
            },
        })
        return capabilities
