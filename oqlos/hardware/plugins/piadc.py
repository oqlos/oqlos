"""
PiADC plugin - ADS1115 16-bit ADC sensor integration.
"""

from __future__ import annotations

import logging
import os
import platform
from typing import Any

import httpx

from oqlos.shared.file_ops import read_text_file_or_empty as _read_text_file

from .base import HardwarePlugin, PluginConfig, PluginHealth, PluginStatus
from ._shared import http_health_check, not_connected_health, health_check_exception, disconnect_http_plugin
from .plugin_http_handlers import http_get_command

logger = logging.getLogger(__name__)


_SENSOR_CHANNEL_ALIASES: dict[str, int] = {
    "ai01": 0,
    "nc-sensor": 0,
    "nc sensor": 0,
    "cisnienie-nc": 0,
    "ciśnienie-nc": 0,
    "nadcisnienie": 0,
    "nadciśnienie": 0,
    "pressure": 0,
    "pressure-sensor": 0,
    "ai02": 1,
    "sc-sensor": 1,
    "sc sensor": 1,
    "cisnienie-sc": 1,
    "ciśnienie-sc": 1,
    "ai03": 2,
    "wc-sensor": 2,
    "wc sensor": 2,
    "cisnienie-wc": 2,
    "ciśnienie-wc": 2,
    "ai04": 3,
    "spare": 3,
}


def _is_raspberry_pi_host() -> bool:
    model = " ".join(
        filter(
            None,
            [
                _read_text_file("/proc/device-tree/model"),
                _read_text_file("/sys/firmware/devicetree/base/model"),
            ],
        )
    ).lower()
    return "raspberry pi" in model


def _requires_remote_rpi_hint(base_url: str, exc: Exception | None = None) -> str:
    detail = f": {exc}" if exc else ""
    if os.getenv("ADS1115_ALLOW_NON_RPI", "false").lower() == "true" or _is_raspberry_pi_host():
        return f"piADC service is not reachable at {base_url}{detail}"
    return (
        f"piADC service is not reachable at {base_url}{detail}. ADS1115 HAT local mode "
        f"requires Raspberry Pi I2C; this host is {platform.machine() or 'unknown'}. "
        "Run piADC on the Raspberry Pi that owns the HAT and set PIADC_URL/OQLOS_PIADC_URL."
    )


def _resolve_sensor_channel(sensor_id: Any) -> int | None:
    sensor_key = str(sensor_id).strip()
    if sensor_key in {"0", "1", "2", "3"}:
        return int(sensor_key)

    normalized_key = sensor_key.lower().replace("_", "-")
    return _SENSOR_CHANNEL_ALIASES.get(normalized_key)


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
        await disconnect_http_plugin(self, "piADC")

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
                reason = details.get("message") or "piADC service is not initialized"
                return PluginHealth(
                    status=PluginStatus.ERROR,
                    message=f"piADC service is not initialized: {reason}",
                    details=details,
                    compatible=False,
                    version=health.version,
                )
            return health
        except Exception as exc:
            if isinstance(exc, (httpx.HTTPError, OSError, RuntimeError)):
                return PluginHealth(
                    status=PluginStatus.ERROR,
                    message=_requires_remote_rpi_hint(self._base_url, exc),
                    compatible=False,
                )
            return health_check_exception(exc)

    async def _read_blocker(self) -> str | None:
        """Return an error message when piADC is reachable but not a real ADC."""
        if not self._client:
            return "Not connected to piADC"

        try:
            resp = await self._client.get(f"{self._base_url}/health")
        except Exception as exc:
            return _requires_remote_rpi_hint(self._base_url, exc)
        if resp.status_code >= 300:
            return f"piADC health check failed: HTTP {resp.status_code}"

        details = resp.json()
        if details.get("mock_mode") is True:
            return "piADC service is in mock_mode; refusing mocked ADC reading"
        if details.get("initialized") is False:
            reason = details.get("message") or "piADC service is not initialized"
            return f"piADC service is not initialized: {reason}"
        return None

    async def execute_command(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute piADC command."""
        if not self._client:
            return {"success": False, "error": "Not connected to piADC"}

        try:
            if command == "read_channel":
                blocker = await self._read_blocker()
                if blocker:
                    return {"success": False, "error": blocker}
                channel = params.get("channel", 0)
                return await http_get_command(self._client, self._base_url, f"/read/{channel}")
            elif command == "read_sensor":
                blocker = await self._read_blocker()
                if blocker:
                    return {"success": False, "error": blocker}
                sensor_id = params.get("sensor_id")
                if not sensor_id:
                    return {"success": False, "error": "sensor_id is required"}
                channel = _resolve_sensor_channel(sensor_id)
                if channel is None:
                    return {"success": False, "error": f"Unknown sensor_id: {sensor_id}"}
                result = await http_get_command(self._client, self._base_url, f"/read/{channel}")
                if not result.get("success"):
                    return result
                data = result.get("data")
                if isinstance(data, dict):
                    return {"success": True, "data": data.get("voltage")}
                return result
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
            "supported_sensors": [
                "AI01",
                "AI02",
                "AI03",
                "AI04",
                "nc-sensor",
                "sc-sensor",
                "wc-sensor",
                "pressure-sensor",
            ],
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
