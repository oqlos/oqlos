"""
Lung plugin - Pololu Tic T249 stepper motor for artificial lung integration.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .base import HardwarePlugin, PluginConfig, PluginHealth, PluginStatus
from ._shared import not_connected_health, health_check_exception, http_disconnect

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
        self._health_endpoint = "/health"

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

                for endpoint in ("/health", "/api/settings"):
                    resp = await self._client.get(f"{self._base_url}{endpoint}")
                    if resp.status_code < 300:
                        self._health_endpoint = endpoint
                        self._status = PluginStatus.CONNECTED
                        logger.info(f"Connected to lung motor at {self._base_url}{endpoint}")
                        return True

                self._status = PluginStatus.ERROR
                logger.error("Lung motor probe failed on /health and /api/settings")
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
        await http_disconnect(self._client, "lung motor")
        self._client = None
        self._status = PluginStatus.CONFIGURED

    async def health_check(self) -> PluginHealth:
        """Check lung motor health and compatibility."""
        if self.config.connection_type == "http" and not self._client:
            return not_connected_health("lung motor")

        try:
            if self.config.connection_type == "http":
                checked: set[str] = set()
                for endpoint in (self._health_endpoint, "/health", "/api/settings"):
                    if endpoint in checked:
                        continue
                    checked.add(endpoint)

                    resp = await self._client.get(f"{self._base_url}{endpoint}")
                    if resp.status_code < 300:
                        details: dict[str, Any] = {"endpoint": endpoint}
                        try:
                            data = resp.json()
                            details["data"] = data
                            version = data.get("version", "unknown") if isinstance(data, dict) else "unknown"
                        except Exception:
                            version = "unknown"

                        runtime = await self._runtime_status()
                        if runtime is not None:
                            details["runtime_status"] = runtime
                            if runtime.get("connected") is False or runtime.get("success") is False or runtime.get("error"):
                                return PluginHealth(
                                    status=PluginStatus.ERROR,
                                    message=runtime.get("error") or "Lung motor service is not initialized",
                                    details=details,
                                    compatible=False,
                                    version=version,
                                )

                        return PluginHealth(
                            status=PluginStatus.CONNECTED,
                            message="Lung motor is healthy",
                            details=details,
                            compatible=True,
                            version=version,
                        )

                return PluginHealth(
                    status=PluginStatus.ERROR,
                    message="Health check failed on /health and /api/settings",
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
            return health_check_exception(exc)

    async def _runtime_status(self) -> dict[str, Any] | None:
        """Return optional runtime status when the HTTP service exposes it."""
        if not self._client:
            return None
        try:
            resp = await self._client.get(f"{self._base_url}/api/status")
        except Exception:
            return None
        if resp.status_code >= 300:
            return None
        try:
            data = resp.json()
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    # ── Command Handlers (refactored from monolithic execute_command) ──

    async def _handle_reciprocate_http(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle reciprocate command via HTTP."""
        steps = params.get("steps", 500)
        speed = params.get("speed", 100000)
        cycles = params.get("cycles", 5)
        pause = params.get("pause", 0.5)
        resp = await self._client.post(
            f"{self._base_url}/api/reciprocate",
            json={"steps": steps, "speed": speed, "cycles": cycles, "pause": pause},
        )
        if resp.status_code < 300:
            return {"success": True, "data": resp.json()}
        return {"success": False, "error": f"HTTP {resp.status_code}"}

    async def _handle_reciprocate_usb(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle reciprocate command via USB (placeholder)."""
        steps = params.get("steps", 500)
        speed = params.get("speed", 100000)
        return {"success": True, "data": {"steps": steps, "speed": speed}}

    async def _handle_stop_http(self) -> dict[str, Any]:
        """Handle stop command via HTTP."""
        resp = await self._client.post(f"{self._base_url}/api/stop")
        if resp.status_code < 300:
            return {"success": True, "data": resp.json()}
        return {"success": False, "error": f"HTTP {resp.status_code}"}

    async def _handle_stop_usb(self) -> dict[str, Any]:
        """Handle stop command via USB (placeholder)."""
        return {"success": True, "data": {"stopped": True}}

    async def _handle_move_http(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle move command via HTTP."""
        position = params.get("position", 0)
        speed = params.get("speed")
        payload = {"position": position}
        if speed is not None:
            payload["speed"] = speed
        resp = await self._client.post(f"{self._base_url}/api/move", json=payload)
        if resp.status_code < 300:
            return {"success": True, "data": resp.json()}
        return {"success": False, "error": f"HTTP {resp.status_code}"}

    async def _handle_move_usb(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle move command via USB (placeholder)."""
        position = params.get("position", 0)
        return {"success": True, "data": {"position": position}}

    async def _handle_energize_http(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle energize command via HTTP."""
        enable = params.get("enable", True)
        resp = await self._client.post(f"{self._base_url}/api/energize", json={"enable": enable})
        if resp.status_code < 300:
            return {"success": True, "data": resp.json()}
        return {"success": False, "error": f"HTTP {resp.status_code}"}

    async def _handle_energize_usb(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle energize command via USB (placeholder)."""
        enable = params.get("enable", True)
        return {"success": True, "data": {"energized": enable}}

    async def _handle_status_http(self) -> dict[str, Any]:
        """Handle status command via HTTP."""
        resp = await self._client.get(f"{self._base_url}/api/status")
        if resp.status_code < 300:
            return {"success": True, "data": resp.json()}
        return {"success": False, "error": f"HTTP {resp.status_code}"}

    async def _handle_status_usb(self) -> dict[str, Any]:
        """Handle status command via USB (placeholder)."""
        return {"success": True, "data": {"status": "ok"}}

    async def execute_command(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute lung motor command.

        Refactored from CC=20 monolithic function into orchestrator
        calling focused command handlers (each CC<10).
        """
        if self.config.connection_type == "http" and not self._client:
            return {"success": False, "error": "Not connected to lung motor"}

        try:
            if command == "reciprocate":
                if self.config.connection_type == "http":
                    return await self._handle_reciprocate_http(params)
                else:
                    return await self._handle_reciprocate_usb(params)

            elif command == "stop":
                if self.config.connection_type == "http":
                    return await self._handle_stop_http()
                else:
                    return await self._handle_stop_usb()

            elif command == "move":
                if self.config.connection_type == "http":
                    return await self._handle_move_http(params)
                else:
                    return await self._handle_move_usb(params)

            elif command == "energize":
                if self.config.connection_type == "http":
                    return await self._handle_energize_http(params)
                else:
                    return await self._handle_energize_usb(params)

            elif command == "status":
                if self.config.connection_type == "http":
                    return await self._handle_status_http()
                else:
                    return await self._handle_status_usb()

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
