"""
Lung plugin - Pololu Tic T249 stepper motor for artificial lung integration.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from .base import HardwarePlugin, PluginConfig, PluginHealth, PluginStatus
from ._shared import (
    PLUGIN_OPERATION_ERRORS as LUNG_OPERATION_ERRORS,
    PLUGIN_PAYLOAD_ERRORS as LUNG_PAYLOAD_ERRORS,
    disconnect_http_plugin,
    not_connected_health,
    plugin_operation_failure,
)
from .plugin_http_handlers import http_get_command, http_post_command
from oqlos.hardware.tic249_units import TIC249_DEFAULT_TARGET_VELOCITY

logger = logging.getLogger(__name__)


_REACH_LIMIT_STOP_TIMEOUT_SECONDS = 14.0
_RUNTIME_STATUS_CACHE_SECONDS = 0.2


def _lung_failure(reason: str, *, status_code: int = 503) -> dict[str, Any]:
    return plugin_operation_failure("motor-tic249", reason, status_code=status_code)


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
        self._runtime_status_cache: dict[str, Any] | None = None
        self._runtime_status_cached_at = 0.0
        self._runtime_status_lock = asyncio.Lock()

    def _invalidate_runtime_status(self) -> None:
        self._runtime_status_cache = None
        self._runtime_status_cached_at = 0.0

    @staticmethod
    def _copy_status_result(result: dict[str, Any]) -> dict[str, Any]:
        copied = dict(result)
        if isinstance(result.get("data"), dict):
            copied["data"] = dict(result["data"])
        if isinstance(result.get("upstream"), dict):
            copied["upstream"] = dict(result["upstream"])
        return copied

    async def _runtime_status_result(self) -> dict[str, Any]:
        """Coalesce and briefly cache the USB-heavy Tic status request."""
        if not self._client:
            return _lung_failure("plugin-unavailable")
        now = time.monotonic()
        cached = self._runtime_status_cache
        if cached is not None and now - self._runtime_status_cached_at < _RUNTIME_STATUS_CACHE_SECONDS:
            return self._copy_status_result(cached)

        async with self._runtime_status_lock:
            now = time.monotonic()
            cached = self._runtime_status_cache
            if cached is not None and now - self._runtime_status_cached_at < _RUNTIME_STATUS_CACHE_SECONDS:
                return self._copy_status_result(cached)
            result = await http_get_command(self._client, self._base_url, "/api/status")
            self._runtime_status_cache = self._copy_status_result(result)
            self._runtime_status_cached_at = time.monotonic()
            return self._copy_status_result(result)

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
        except LUNG_OPERATION_ERRORS as exc:
            self._status = PluginStatus.ERROR
            logger.error(
                "Lung motor connection failed exception_type=%s",
                type(exc).__name__,
            )
            return False

    async def disconnect(self) -> None:
        """Disconnect from lung motor service."""
        self._invalidate_runtime_status()
        await disconnect_http_plugin(self, "lung motor")

    async def _health_check_http(self) -> PluginHealth:
        """Try each endpoint in order, return health on first 2xx response."""
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
                except LUNG_PAYLOAD_ERRORS:
                    version = "unknown"

                runtime = await self._runtime_status()
                if runtime is not None:
                    details["runtime_status"] = runtime
                    if (
                        runtime.get("connected") is False
                        or runtime.get("success") is False
                        or runtime.get("error")
                    ):
                        return PluginHealth(
                            status=PluginStatus.ERROR,
                            message=runtime.get("error") or "Lung motor service is not initialized",
                            details=details,
                            compatible=False,
                            version=version,
                        )
                    alert = self._position_uncertain_alert(runtime)
                    if alert:
                        details["operator_alerts"] = [
                            {
                                "issue_code": "hw_tic249_position_uncertain",
                                "message": alert,
                            }
                        ]

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

    async def health_check(self) -> PluginHealth:
        """Check lung motor health and compatibility."""
        if self.config.connection_type == "http" and not self._client:
            return not_connected_health("lung motor")

        try:
            if self.config.connection_type == "http":
                return await self._health_check_http()
            return PluginHealth(
                status=PluginStatus.CONNECTED,
                message="Lung motor (USB) is healthy",
                compatible=True,
            )
        except LUNG_OPERATION_ERRORS as exc:
            logger.error(
                "Lung motor health check failed exception_type=%s",
                type(exc).__name__,
            )
            return PluginHealth(
                status=PluginStatus.ERROR,
                message="Lung motor health check failed",
                compatible=False,
            )

    async def _runtime_status(self) -> dict[str, Any] | None:
        """Return optional runtime status when the HTTP service exposes it."""
        if not self._client:
            return None
        try:
            result = await self._runtime_status_result()
        except LUNG_OPERATION_ERRORS:
            return None
        data = result.get("data")
        if result.get("success") is True and isinstance(data, dict):
            return dict(data)
        upstream = result.get("upstream")
        failure = dict(upstream) if isinstance(upstream, dict) else {}
        failure.setdefault("success", False)
        failure.setdefault(
            "error",
            str(result.get("error") or "Lung motor runtime status is invalid"),
        )
        failure.setdefault("code", str(result.get("code") or "C2004-HW-0012"))
        failure.setdefault(
            "error_code", str(result.get("error_code") or "C2004-HW-0012")
        )
        failure.setdefault("status_code", int(result.get("status_code") or 503))
        return failure

    @staticmethod
    def _runtime_block_reason(status: dict[str, Any] | None) -> str | None:
        """Return a user-facing reason when runtime state indicates no motion is possible."""
        if not isinstance(status, dict):
            return None

        if status.get("connected") is False:
            return "Lung motor is not connected"
        if status.get("success") is False:
            return "Lung motor runtime status is unavailable"
        if status.get("motor_driver_error"):
            return "Motor driver error is active"
        if status.get("low_vin"):
            return "Motor supply voltage is too low"

        # ready=False is a standby/safe-start state after stop or de-energize.
        # The rpi-motor-tic249 service prepares the Tic before motion, so it is
        # not a blocker by itself.

        # Safety stop state observed in the field: both limits active => Tic blocks movement.
        if status.get("forward_limit_active") and status.get("reverse_limit_active"):
            return "Both limit switches are active; movement is blocked"

        # position_uncertain is reported as an operator alert in health check, but does not block relative reciprocate motion.
        return None


    @staticmethod
    def _position_uncertain_alert(status: dict[str, Any] | None) -> str | None:
        """Polish operator text when Tic249 reports an untrusted position."""
        if not isinstance(status, dict) or not status.get("position_uncertain"):
            return None
        logger.warning(
            "tic249 issue_code=hw_tic249_position_uncertain "
            "position=%s reverse_limit=%s forward_limit=%s energized=%s",
            status.get("position"),
            status.get("reverse_limit_active"),
            status.get("forward_limit_active"),
            status.get("energized"),
        )
        if status.get("forward_limit_active") or status.get("reverse_limit_active"):
            return "Pozycja silnika niepewna — wykonaj homing do krańcówki."
        return (
            "Pozycja silnika jest niepewna i żadna krańcówka nie jest aktywna. "
            "Sprawdź okablowanie reverse i mapę pinów OQL/NVM albo wykonaj "
            "homing przed ruchem AL."
        )

    # ── Command Handlers (refactored from monolithic execute_command) ──

    async def _handle_reciprocate_http(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle reciprocate command via HTTP."""
        steps = params.get("steps", 500)
        speed = params.get("speed", TIC249_DEFAULT_TARGET_VELOCITY)
        cycles = params.get("cycles", 5)
        pause = params.get("pause", 0.5)
        payload: dict[str, Any] = {
            "steps": steps,
            "speed": speed,
            "cycles": cycles,
            "pause": pause,
        }
        for key in (
            "direction",
            "start_direction",
            "acceleration",
            "ramp_seconds",
            "ramp_time_sec",
            "ramp_time",
            "limit_mode",
        ):
            if key in params:
                payload[key] = params[key]

        runtime = await self._runtime_status()
        blocked_reason = self._runtime_block_reason(runtime)
        if blocked_reason:
            payload = {
                "success": False,
                "error": blocked_reason,
                "code": "C2004-HW-0012",
                "error_code": "C2004-HW-0012",
                "status_code": 503,
                "architecture": "SOA",
                "component": "motor-tic249",
                "stage": "adapter.preflight",
                "data": {},
            }
            if runtime and runtime.get("position_uncertain"):
                payload["issue_code"] = "hw_tic249_position_uncertain"
            return payload

        self._invalidate_runtime_status()
        resp = await http_post_command(
            self._client,
            self._base_url,
            "/api/reciprocate",
            json_body=payload,
        )
        return resp

    async def _handle_reciprocate_usb(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle reciprocate command via USB (placeholder)."""
        steps = params.get("steps", 500)
        speed = params.get("speed", TIC249_DEFAULT_TARGET_VELOCITY)
        return {"success": True, "data": {"steps": steps, "speed": speed}}

    async def _handle_stroke_sequence_http(self, params: dict[str, Any]) -> dict[str, Any]:
        """Forward the strict human-unit, zero-dwell stroke sequence contract."""
        runtime = await self._runtime_status()
        blocked_reason = self._runtime_block_reason(runtime)
        if blocked_reason:
            return _lung_failure(blocked_reason)
        self._invalidate_runtime_status()
        return await http_post_command(
            self._client,
            self._base_url,
            "/api/stroke-sequence",
            json_body=dict(params),
        )

    async def _handle_stop_http(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Handle stop command via HTTP."""
        payload: dict[str, Any] = {}
        params = params or {}
        reach_limit = params.get("stop_mode") == "reach_limit" or params.get("stop_at_limit")
        if reach_limit:
            payload["stop_mode"] = "reach_limit"
        elif params.get("stop_at_limit") is False:
            # Preserve an explicit immediate-stop override.  Sending an empty
            # body makes the Tic249 sidecar fall back to its persistent
            # stop_at_limit setting, which can turn HUI STOP into a slow
            # reach-limit move and exceed the HTTP timeout.
            payload["stop_at_limit"] = False
        self._invalidate_runtime_status()
        return await http_post_command(
            self._client,
            self._base_url,
            "/api/stop",
            json_body=payload or None,
            timeout=(
                max(float(self.config.timeout), _REACH_LIMIT_STOP_TIMEOUT_SECONDS)
                if reach_limit
                else None
            ),
        )

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
        self._invalidate_runtime_status()
        return await http_post_command(self._client, self._base_url, "/api/move", json_body=payload)

    async def _handle_move_usb(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle move command via USB (placeholder)."""
        position = params.get("position", 0)
        return {"success": True, "data": {"position": position}}

    async def _handle_energize_http(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle energize command via HTTP."""
        enable = params.get("enable", True)
        self._invalidate_runtime_status()
        return await http_post_command(
            self._client,
            self._base_url,
            "/api/energize",
            json_body={"enable": enable},
        )

    async def _handle_energize_usb(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle energize command via USB (placeholder)."""
        enable = params.get("enable", True)
        return {"success": True, "data": {"energized": enable}}

    async def _handle_status_http(self) -> dict[str, Any]:
        """Handle status command via HTTP."""
        return await self._runtime_status_result()

    async def _handle_status_usb(self) -> dict[str, Any]:
        """Handle status command via USB (placeholder)."""
        return {"success": True, "data": {"status": "ok"}}

    async def execute_command(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute lung motor command.

        Refactored from CC=20 monolithic function into orchestrator
        calling focused command handlers (each CC<10).
        """
        if self.config.connection_type == "http" and not self._client:
            return _lung_failure("plugin-unavailable")

        try:
            if command == "reciprocate":
                if self.config.connection_type == "http":
                    return await self._handle_reciprocate_http(params)
                return await self._handle_reciprocate_usb(params)

            elif command == "stroke_sequence":
                if self.config.connection_type == "http":
                    return await self._handle_stroke_sequence_http(params)
                return _lung_failure("stroke-sequence-requires-http", status_code=422)

            elif command == "stop":
                if self.config.connection_type == "http":
                    return await self._handle_stop_http(params)
                return await self._handle_stop_usb()

            elif command == "move":
                if self.config.connection_type == "http":
                    return await self._handle_move_http(params)
                return await self._handle_move_usb(params)

            elif command == "energize":
                if self.config.connection_type == "http":
                    return await self._handle_energize_http(params)
                return await self._handle_energize_usb(params)

            elif command == "status":
                if self.config.connection_type == "http":
                    return await self._handle_status_http()
                return await self._handle_status_usb()

            else:
                return _lung_failure("unsupported-command", status_code=422)

        except LUNG_OPERATION_ERRORS as exc:
            logger.error(
                "Lung motor command failed exception_type=%s",
                type(exc).__name__,
            )
            return _lung_failure("command-failed")

    @classmethod
    def get_capabilities(cls) -> dict[str, Any]:
        """Return lung plugin capabilities."""
        capabilities = super().get_capabilities()
        capabilities.update({
            "supported_commands": [
                "reciprocate",
                "stroke_sequence",
                "stop",
                "move",
                "energize",
                "status",
            ],
            "capabilities": ["reciprocate", "zero-dwell-stroke-sequence", "homing", "limit-switches"],
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
