"""
Motor plugin - DFRobot DRI0050 PWM motor driver integration.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from typing import Any

import httpx

from .base import HardwarePlugin, PluginConfig, PluginHealth, PluginStatus
from ._shared import http_health_check, not_connected_health, health_check_exception, http_disconnect

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
    PLUGIN_DESCRIPTION = "PWM motor & LED strip driver via CLI or HTTP"
    REQUIRED_PYTHON_PACKAGES = []
    SUPPORTED_PROTOCOLS = ["http", "cli", "modbus-rtu"]

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
        self._base_url = self.config.connection_params.get("base_url", "http://localhost:49055").rstrip("/")
        self._cli_command = self.config.connection_params.get("command")
        self._cli_port = self.config.connection_params.get("port")

    def validate_config(self) -> list[str]:
        """Validate motor-specific configuration."""
        errors = []
        if self.config.connection_type not in ["http", "cli", "modbus-rtu"]:
            errors.append("motor currently supports http, cli or modbus-rtu connection types")

        if self.config.connection_type == "http":
            base_url = self.config.connection_params.get("base_url")
            if not base_url:
                errors.append("base_url is required in connection_params for http connection")
            elif not base_url.startswith(("http://", "https://")):
                errors.append("base_url must start with http:// or https://")
        elif self.config.connection_type == "cli":
            command = self.config.connection_params.get("command")
            if not command:
                errors.append("command is required in connection_params for cli connection")
            port = self.config.connection_params.get("port")
            if not port:
                errors.append("port is required in connection_params for cli connection")
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
            elif self.config.connection_type == "cli":
                # Test CLI command availability
                proc = await asyncio.create_subprocess_exec(
                    self._cli_command, self._cli_port,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                await asyncio.wait_for(proc.wait(), timeout=self.config.timeout)
                self._status = PluginStatus.CONNECTED
                logger.info(f"Connected to motor via CLI: {self._cli_command}")
                return True
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
        await http_disconnect(self._client, "motor")
        self._client = None
        self._status = PluginStatus.CONFIGURED

    async def health_check(self) -> PluginHealth:
        """Check motor health and compatibility."""
        if self.config.connection_type == "http" and not self._client:
            return not_connected_health("motor")

        try:
            if self.config.connection_type == "http":
                return await http_health_check(self._client, self._base_url, "Motor")
            else:
                # Modbus RTU health check would be implemented here
                return PluginHealth(
                    status=PluginStatus.CONNECTED,
                    message="Motor (modbus-rtu) is healthy",
                    compatible=True,
                )
        except Exception as exc:
            return health_check_exception(exc)

    # ── Command Handlers (refactored from monolithic execute_command) ──

    def _validate_power_pct(self, power_pct: float) -> tuple[bool, float, str | None]:
        """Validate and convert power percentage using peripheral config."""
        peripheral = self.config.get_peripheral("speed")
        if peripheral:
            is_valid, error_msg = peripheral.validate_value(power_pct)
            if not is_valid:
                return False, power_pct, error_msg
            return True, peripheral.convert_value(power_pct), None
        else:
            # Fallback validation
            if not 0 <= power_pct <= 100:
                return False, power_pct, "power_pct must be between 0 and 100"
            return True, power_pct, None

    async def _handle_set_speed_http(self, power_pct: float, start_time: float) -> dict[str, Any]:
        """Handle set_speed command via HTTP."""
        if power_pct <= 0:
            resp = await self._client.post(f"{self._base_url}/api/stop")
        else:
            resp = await self._client.post(
                f"{self._base_url}/api/speed",
                json={"power_pct": power_pct},
            )
        if resp.status_code < 300:
            data = resp.json()
            duration_ms = (time.monotonic() - start_time) * 1000
            return {
                "success": True,
                "data": {
                    "power_pct": power_pct,
                    "pwm_value": data.get("pwm_value", power_pct * 10),
                    "voltage": data.get("voltage", 0.0),
                    "current": data.get("current", 0.0),
                    "duration_ms": duration_ms,
                    "timestamp": time.time(),
                },
            }
        return {"success": False, "error": f"HTTP {resp.status_code}"}

    async def _handle_set_speed_cli(self, power_pct: float, start_time: float) -> dict[str, Any]:
        """Handle set_speed command via CLI."""
        duty_cycle = power_pct
        cmd_args = [self._cli_command, self._cli_port, "--duty", str(duty_cycle), "--enable", "1"]
        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.config.timeout)
        duration_ms = (time.monotonic() - start_time) * 1000
        if proc.returncode == 0:
            return {
                "success": True,
                "data": {
                    "power_pct": power_pct,
                    "pwm_value": duty_cycle,
                    "duration_ms": duration_ms,
                    "timestamp": time.time(),
                    "stdout": stdout.decode().strip(),
                },
            }
        return {"success": False, "error": stderr.decode().strip()}

    async def _handle_set_speed_modbus(self, power_pct: float, start_time: float) -> dict[str, Any]:
        """Handle set_speed command via Modbus RTU (placeholder)."""
        duration_ms = (time.monotonic() - start_time) * 1000
        return {
            "success": True,
            "data": {
                "power_pct": power_pct,
                "pwm_value": power_pct * 10,
                "duration_ms": duration_ms,
                "timestamp": time.time(),
            },
        }

    async def _handle_stop_http(self, start_time: float) -> dict[str, Any]:
        """Handle stop command via HTTP."""
        resp = await self._client.post(f"{self._base_url}/api/stop")
        if resp.status_code < 300:
            data = resp.json()
            duration_ms = (time.monotonic() - start_time) * 1000
            return {
                "success": True,
                "data": {
                    "stopped": True,
                    "pwm_value": data.get("pwm_value", 0),
                    "voltage": data.get("voltage", 0.0),
                    "current": data.get("current", 0.0),
                    "duration_ms": duration_ms,
                    "timestamp": time.time(),
                },
            }
        return {"success": False, "error": f"HTTP {resp.status_code}"}

    async def _handle_stop_cli(self, start_time: float) -> dict[str, Any]:
        """Handle stop command via CLI."""
        cmd_args = [self._cli_command, self._cli_port, "--enable", "0"]
        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.config.timeout)
        duration_ms = (time.monotonic() - start_time) * 1000
        if proc.returncode == 0:
            return {
                "success": True,
                "data": {
                    "stopped": True,
                    "duration_ms": duration_ms,
                    "timestamp": time.time(),
                    "stdout": stdout.decode().strip(),
                },
            }
        return {"success": False, "error": stderr.decode().strip()}

    async def _handle_stop_modbus(self, start_time: float) -> dict[str, Any]:
        """Handle stop command via Modbus RTU (placeholder)."""
        duration_ms = (time.monotonic() - start_time) * 1000
        return {
            "success": True,
            "data": {
                "stopped": True,
                "duration_ms": duration_ms,
                "timestamp": time.time(),
            },
        }

    async def _handle_status_http(self, start_time: float) -> dict[str, Any]:
        """Handle status command via HTTP."""
        resp = await self._client.get(f"{self._base_url}/api/status")
        if resp.status_code < 300:
            data = resp.json()
            duration_ms = (time.monotonic() - start_time) * 1000
            return {
                "success": True,
                "data": {
                    "pwm_value": data.get("pwm_value", 0),
                    "voltage": data.get("voltage", 0.0),
                    "current": data.get("current", 0.0),
                    "power_pct": data.get("power_pct", 0),
                    "temperature": data.get("temperature", 0.0),
                    "duration_ms": duration_ms,
                    "timestamp": time.time(),
                },
            }
        return {"success": False, "error": f"HTTP {resp.status_code}"}

    async def _handle_status_cli(self, start_time: float) -> dict[str, Any]:
        """Handle status command via CLI (returns basic info)."""
        duration_ms = (time.monotonic() - start_time) * 1000
        return {
            "success": True,
            "data": {
                "mode": "cli",
                "command": self._cli_command,
                "port": self._cli_port,
                "duration_ms": duration_ms,
                "timestamp": time.time(),
            },
        }

    async def _handle_status_modbus(self, start_time: float) -> dict[str, Any]:
        """Handle status command via Modbus RTU (placeholder)."""
        duration_ms = (time.monotonic() - start_time) * 1000
        return {
            "success": True,
            "data": {
                "duration_ms": duration_ms,
                "timestamp": time.time(),
            },
        }

    async def execute_command(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute motor command with detailed driver data.

        Refactored from CC=23 monolithic function into orchestrator
        calling focused command handlers (each CC<10).
        """
        if self.config.connection_type == "http" and not self._client:
            return {"success": False, "error": "Not connected to motor"}

        start_time = time.monotonic()

        try:
            if command == "set_speed":
                power_pct = params.get("power_pct", 0)
                is_valid, converted_pct, error_msg = self._validate_power_pct(power_pct)
                if not is_valid:
                    return {"success": False, "error": error_msg}

                if self.config.connection_type == "http":
                    return await self._handle_set_speed_http(converted_pct, start_time)
                elif self.config.connection_type == "cli":
                    return await self._handle_set_speed_cli(converted_pct, start_time)
                else:
                    return await self._handle_set_speed_modbus(converted_pct, start_time)

            elif command == "stop":
                if self.config.connection_type == "http":
                    return await self._handle_stop_http(start_time)
                elif self.config.connection_type == "cli":
                    return await self._handle_stop_cli(start_time)
                else:
                    return await self._handle_stop_modbus(start_time)

            elif command == "status":
                if self.config.connection_type == "http":
                    return await self._handle_status_http(start_time)
                elif self.config.connection_type == "cli":
                    return await self._handle_status_cli(start_time)
                else:
                    return await self._handle_status_modbus(start_time)

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
