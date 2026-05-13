"""
Motor plugin - DFRobot DRI0050 PWM motor driver integration.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from typing import Any
from urllib.parse import urlparse

import httpx

try:
    from pimodbus.client import get_rtu_bus
    from pimodbus.config import RtuBusSettings
    _HAS_PIMODBUS = True
except ImportError:  # pragma: no cover
    get_rtu_bus = None  # type: ignore
    RtuBusSettings = None  # type: ignore
    _HAS_PIMODBUS = False

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
        # pimodbus shared RTU bus (singleton — same bus as modbus-adc/io)
        self._bus: Any = None
        params = self.config.connection_params
        self._mb_serial_port: str = params.get("serial_port", "/dev/modbus-bus")
        self._mb_baud: int = int(params.get("baudrate", 9600))
        self._mb_parity: str = str(params.get("parity", "N"))
        self._mb_slave: int = int(params.get("device_id", 50))  # DRI0050 default 0x32
        self._mb_pid_reg: int = int(params.get("pid_register", 0x0000))
        self._mb_duty_reg: int = int(params.get("duty_register", 0x0006))
        self._mb_freq_reg: int = int(params.get("frequency_register", 0x0007))
        self._mb_enable_reg: int = int(params.get("enable_register", 0x0008))

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
                # Modbus RTU via pimodbus shared bus (singleton)
                if not _HAS_PIMODBUS:
                    self._status = PluginStatus.ERROR
                    logger.error("pimodbus not installed; cannot use modbus-rtu motor")
                    return False
                settings = RtuBusSettings(
                    serial_port=self._mb_serial_port,
                    baudrate=self._mb_baud,
                    parity=self._mb_parity,
                    timeout=self.config.timeout,
                )
                self._bus = get_rtu_bus(settings)
                if await self._bus.connect():
                    self._status = PluginStatus.CONNECTED
                    logger.info(
                        "Connected to motor via pimodbus on %s slave=%d",
                        self._mb_serial_port,
                        self._mb_slave,
                    )
                    return True
                else:
                    self._status = PluginStatus.ERROR
                    logger.error(
                        "pimodbus connect failed for motor on %s", self._mb_serial_port
                    )
                    return False
        except Exception as exc:
            self._status = PluginStatus.ERROR
            logger.error(f"Failed to connect to motor: {exc}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from motor service."""
        await http_disconnect(self._client, "motor")
        self._client = None
        if self._bus is not None:
            # Don't close the shared bus — other plugins use it.
            # Just drop our reference.
            self._bus = None
        self._status = PluginStatus.CONFIGURED

    async def health_check(self) -> PluginHealth:
        """Check motor health and compatibility."""
        if self.config.connection_type == "http" and not self._client:
            return not_connected_health("motor")

        try:
            if self.config.connection_type == "http":
                health = await http_health_check(self._client, self._base_url, "Motor")
                details = health.details if isinstance(health.details, dict) else {}
                port = details.get("port")
                if isinstance(port, str) and port.startswith("/dev/") and self._base_url_is_local():
                    if not os.path.exists(port):
                        return PluginHealth(
                            status=PluginStatus.ERROR,
                            message=f"Motor service reports missing serial port: {port}",
                            details=details,
                            compatible=False,
                            version=health.version,
                        )
                return health
            elif self.config.connection_type == "modbus-rtu":
                if self._bus is None:
                    return PluginHealth(
                        status=PluginStatus.ERROR,
                        message="Motor modbus bus not connected",
                        compatible=False,
                    )
                try:
                    rr = await self._bus.call(
                        "read_holding_registers",
                        address=self._mb_pid_reg,
                        count=1,
                        device_id=self._mb_slave,
                    )
                except asyncio.TimeoutError:
                    return PluginHealth(
                        status=PluginStatus.ERROR,
                        message=f"Motor (modbus-rtu) PID read timed out (slave={self._mb_slave}, reg=0x{self._mb_pid_reg:04X})",
                        details={"slave": self._mb_slave, "register": self._mb_pid_reg},
                        compatible=False,
                    )
                if rr is None or (hasattr(rr, "isError") and rr.isError()):
                    return PluginHealth(
                        status=PluginStatus.ERROR,
                        message=f"Motor (modbus-rtu) PID read failed: {rr}",
                        details={"slave": self._mb_slave, "register": self._mb_pid_reg},
                        compatible=False,
                    )
                pid = getattr(rr, "registers", [None])[0]
                return PluginHealth(
                    status=PluginStatus.CONNECTED,
                    message=f"Motor (modbus-rtu) is healthy, PID=0x{pid:04X}" if pid is not None else "Motor (modbus-rtu) connected (PID unknown)",
                    details={"slave": self._mb_slave, "pid": pid},
                    compatible=True,
                )
            else:
                return PluginHealth(
                    status=PluginStatus.CONNECTED,
                    message="Motor is healthy (no health probe for this transport)",
                    compatible=True,
                )
        except Exception as exc:
            return health_check_exception(exc)

    def _base_url_is_local(self) -> bool:
        host = (urlparse(self._base_url).hostname or "").lower()
        return host in {"", "localhost", "127.0.0.1", "::1"}

    # ── Command Handlers (refactored from monolithic execute_command) ──

    def _validate_power_pct(self, power_pct: float) -> tuple[bool, float, str | None]:
        """Validate pump power percentage.

        The HTTP DRI0050 service accepts ``power_pct`` directly as 0-100%.
        Peripheral conversions such as l/min -> duty belong in higher-level
        scenario mapping, not in this low-level percent command.
        """
        try:
            normalized = float(power_pct)
        except (TypeError, ValueError):
            return False, 0.0, "power_pct must be a number"

        if not 0 <= normalized <= 100:
            return False, normalized, "power_pct must be between 0 and 100"
        return True, normalized, None

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
        """Handle set_speed via Modbus RTU.

        Writes Duty (0-1000 = 0-100%) and Enable=1 to DRI0050 holding registers.
        """
        if self._bus is None:
            return {"success": False, "error": "Motor modbus bus not connected"}
        duty_value = int(round(max(0.0, min(100.0, power_pct)) * 2.55))  # 0-100% → 0-255
        try:
            wr_duty = await self._bus.call(
                "write_register",
                address=self._mb_duty_reg,
                value=duty_value,
                device_id=self._mb_slave,
            )
            if hasattr(wr_duty, "isError") and wr_duty.isError():
                return {"success": False, "error": f"write Duty failed: {wr_duty}"}
            wr_en = await self._bus.call(
                "write_register",
                address=self._mb_enable_reg,
                value=1,
                device_id=self._mb_slave,
            )
            if hasattr(wr_en, "isError") and wr_en.isError():
                return {"success": False, "error": f"write Enable failed: {wr_en}"}
        except Exception as exc:
            return {"success": False, "error": f"modbus exception: {exc}"}
        duration_ms = (time.monotonic() - start_time) * 1000
        return {
            "success": True,
            "data": {
                "power_pct": power_pct,
                "pwm_value": duty_value,
                "duty_register": self._mb_duty_reg,
                "slave": self._mb_slave,
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
        """Handle stop via Modbus RTU — Duty=0 + Enable=0."""
        if self._bus is None:
            return {"success": False, "error": "Motor modbus bus not connected"}
        try:
            await self._bus.call(
                "write_register",
                address=self._mb_duty_reg,
                value=0,
                device_id=self._mb_slave,
            )
            await self._bus.call(
                "write_register",
                address=self._mb_enable_reg,
                value=0,
                device_id=self._mb_slave,
            )
        except Exception as exc:
            return {"success": False, "error": f"modbus exception: {exc}"}
        duration_ms = (time.monotonic() - start_time) * 1000
        return {
            "success": True,
            "data": {
                "stopped": True,
                "slave": self._mb_slave,
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
        """Read Duty + Enable holding registers from DRI0050."""
        if self._bus is None:
            return {"success": False, "error": "Motor modbus bus not connected"}
        try:
            rr = await self._bus.call(
                "read_holding_registers",
                address=self._mb_duty_reg,
                count=3,  # Duty, Frequency, Enable (consecutive 0x07-0x09)
                device_id=self._mb_slave,
            )
            if hasattr(rr, "isError") and rr.isError():
                return {"success": False, "error": f"read failed: {rr}"}
            regs = getattr(rr, "registers", [])
            duty = regs[0] if len(regs) > 0 else 0
            freq = regs[1] if len(regs) > 1 else 0
            enable = regs[2] if len(regs) > 2 else 0
        except Exception as exc:
            return {"success": False, "error": f"modbus exception: {exc}"}
        duration_ms = (time.monotonic() - start_time) * 1000
        return {
            "success": True,
            "data": {
                "duty": duty,
                "power_pct": round(duty / 2.55, 2),
                "frequency_hz": freq,
                "enabled": bool(enable),
                "slave": self._mb_slave,
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
