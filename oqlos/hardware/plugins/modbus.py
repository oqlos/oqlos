"""
Modbus plugin - Waveshare Modbus RTU IO 8CH integration.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .base import HardwarePlugin, PluginConfig, PluginHealth, PluginStatus

logger = logging.getLogger(__name__)


class ModbusPlugin(HardwarePlugin):
    """
    Plugin for Waveshare Modbus RTU IO 8CH valve controller.

    Configuration:
        connection_type: "modbus-rtu" or "modbus-tcp"
        connection_params:
            serial_port: e.g., "/dev/ttyACM0" (for RTU)
            baudrate: e.g., 19200 (for RTU)
            parity: e.g., "N" (for RTU)
            host: e.g., "localhost" (for TCP)
            port: e.g., 502 (for TCP)
    """

    PLUGIN_ID = "modbus-io"
    PLUGIN_NAME = "Waveshare Modbus RTU IO 8CH"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_DESCRIPTION = "8DI + 8DO industrial I/O module — valve & signal control"
    REQUIRED_PYTHON_PACKAGES = ["pymodbus"]
    SUPPORTED_PROTOCOLS = ["modbus-rtu", "modbus-tcp"]

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self._client: Any = None
        self._bus: Any = None
        self._mode = "unknown"

    def validate_config(self) -> list[str]:
        """Validate modbus-specific configuration."""
        errors = []
        if self.config.connection_type == "modbus-rtu":
            serial_port = self.config.connection_params.get("serial_port")
            if not serial_port:
                errors.append("serial_port is required in connection_params for modbus-rtu")
            baudrate = self.config.connection_params.get("baudrate", 19200)
            if not isinstance(baudrate, int) or baudrate <= 0:
                errors.append("baudrate must be a positive integer")
            parity = self.config.connection_params.get("parity", "N")
            if parity not in ["N", "E", "O"]:
                errors.append("parity must be N, E, or O")
            device_id = self.config.connection_params.get("device_id", 1)
            if not isinstance(device_id, int) or device_id <= 0:
                errors.append("device_id must be a positive integer")
        elif self.config.connection_type == "modbus-tcp":
            host = self.config.connection_params.get("host")
            if not host:
                errors.append("host is required in connection_params for modbus-tcp")
            port = self.config.connection_params.get("port", 502)
            if not isinstance(port, int) or port <= 0 or port > 65535:
                errors.append("port must be a valid port number (1-65535)")
            device_id = self.config.connection_params.get("device_id", 1)
            if not isinstance(device_id, int) or device_id <= 0:
                errors.append("device_id must be a positive integer")
        else:
            errors.append("modbus plugin supports modbus-rtu or modbus-tcp connection types")

        return errors

    async def connect(self) -> bool:
        """Connect to modbus device."""
        try:
            if self.config.connection_type == "modbus-rtu":
                try:
                    from pimodbus.client import get_rtu_bus
                    from pimodbus.config import RtuBusSettings
                except ImportError:
                    logger.error("pimodbus not installed for modbus-rtu connection")
                    self._status = PluginStatus.INCOMPATIBLE
                    return False

                serial_port = self.config.connection_params.get("serial_port", "/dev/ttyACM0")
                baudrate = self.config.connection_params.get("baudrate", 19200)
                parity = self.config.connection_params.get("parity", "N")
                settings = RtuBusSettings(
                    serial_port=serial_port,
                    baudrate=baudrate,
                    parity=parity,
                    timeout=self.config.timeout,
                )
                self._bus = get_rtu_bus(settings)
                if await self._bus.connect():
                    self._mode = "rtu"
                    self._status = PluginStatus.CONNECTED
                    logger.info(f"Connected to modbus-rtu at {serial_port}@{baudrate} 8{parity}1")
                    return True
                else:
                    self._status = PluginStatus.ERROR
                    logger.error("Failed to connect to modbus-rtu")
                    return False
            elif self.config.connection_type == "modbus-tcp":
                try:
                    from pymodbus.client import AsyncModbusTcpClient
                except ImportError:
                    logger.error("pymodbus not installed for modbus-tcp connection")
                    self._status = PluginStatus.INCOMPATIBLE
                    return False

                host = self.config.connection_params.get("host", "localhost")
                port = self.config.connection_params.get("port", 502)

                self._client = AsyncModbusTcpClient(host=host, port=port)
                await self._client.connect()
                self._mode = "tcp"
                self._status = PluginStatus.CONNECTED
                logger.info(f"Connected to modbus-tcp at {host}:{port}")
                return True
            else:
                self._status = PluginStatus.ERROR
                return False
        except Exception as exc:
            self._status = PluginStatus.ERROR
            logger.error(f"Failed to connect to modbus: {exc}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from modbus device."""
        if self._bus:
            await self._bus.close()
            self._bus = None
        if self._client:
            if self._mode == "rtu":
                self._client.close()
            elif self._mode == "tcp":
                await self._client.close()
            self._client = None
        self._status = PluginStatus.CONFIGURED
        logger.info("Disconnected from modbus")

    async def health_check(self) -> PluginHealth:
        """Check modbus health and compatibility."""
        if not self._client and not self._bus:
            return PluginHealth(
                status=PluginStatus.ERROR,
                message="Not connected to modbus",
                compatible=False,
            )

        try:
            # Try to read a coil to test connection
            if self._mode == "rtu":
                try:
                    result = await self._rtu_call(
                        "read_coils",
                        address=0,
                        count=1,
                        device_id=self._device_id(),
                    )
                except asyncio.TimeoutError:
                    return PluginHealth(
                        status=PluginStatus.ERROR,
                        message=f"Modbus RTU read_coils timed out after {self._rtu_timeout():.1f}s",
                        compatible=False,
                    )
                if result and not result.isError():
                    return PluginHealth(
                        status=PluginStatus.CONNECTED,
                        message="Modbus RTU is healthy",
                        details={"mode": "rtu", "device_id": self._device_id()},
                        compatible=True,
                    )
                else:
                    return PluginHealth(
                        status=PluginStatus.ERROR,
                        message="Modbus RTU read_coils failed",
                        compatible=False,
                    )
            elif self._mode == "tcp":
                result = await self._client.read_coils(0, count=1, device_id=self._device_id())
                if not result.isError():
                    return PluginHealth(
                        status=PluginStatus.CONNECTED,
                        message="Modbus TCP is healthy",
                        details={"mode": "tcp", "device_id": self._device_id()},
                        compatible=True,
                    )
                else:
                    return PluginHealth(
                        status=PluginStatus.ERROR,
                        message="Modbus TCP read_coils failed",
                        compatible=False,
                    )
        except Exception as exc:
            return PluginHealth(
                status=PluginStatus.ERROR,
                message=f"Health check exception: {exc}",
                compatible=False,
            )

        return PluginHealth(status=PluginStatus.ERROR, message="Unknown mode", compatible=False)

    async def execute_command(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute modbus command."""
        if not self._client and not self._bus:
            return {"success": False, "error": "Not connected to modbus"}

        try:
            if command == "set_coil":
                coil = params.get("coil", 0)
                value = params.get("value", False)
                if not isinstance(coil, int) or coil < 0:
                    return {"success": False, "error": "coil must be a non-negative integer"}

                if self._mode == "rtu":
                    result = await self._rtu_call(
                        "write_coil",
                        address=coil,
                        value=value,
                        device_id=self._device_id(),
                    )
                    success = hasattr(result, "function_code") and not getattr(result, "isError", lambda: True)()
                else:
                    result = await self._client.write_coil(coil, value, device_id=self._device_id())
                    success = not result.isError()

                if success:
                    return {"success": True, "data": {"coil": coil, "value": value}}
                else:
                    return {"success": False, "error": str(result)}
            elif command == "set_valve":
                valve_id = params.get("valve_id")
                value = params.get("value", False)
                if not valve_id:
                    return {"success": False, "error": "valve_id is required"}

                # Map valve IDs to coil addresses
                valve_coil_map = {
                    "valve-1": 0, "valve-2": 1, "valve-3": 2, "valve-4": 3,
                    "valve-5": 4, "valve-6": 5, "valve-7": 6, "valve-8": 7,
                    "valve-nc": 0, "valve-sc": 1, "valve-wc": 2,
                }
                coil = valve_coil_map.get(valve_id)
                if coil is None:
                    return {"success": False, "error": f"Unknown valve_id: {valve_id}"}

                return await self.execute_command("set_coil", {"coil": coil, "value": value})
            else:
                return {"success": False, "error": f"Unknown command: {command}"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _rtu_timeout(self) -> float:
        try:
            return max(0.1, float(self.config.timeout))
        except (TypeError, ValueError):
            return 2.0

    async def _rtu_call(self, method_name: str, **kwargs: Any) -> Any:
        if self._bus is not None:
            method = getattr(self._bus, method_name)
            return await method(timeout=self._rtu_timeout(), **kwargs)
        return await asyncio.wait_for(
            asyncio.to_thread(getattr(self._client, method_name), **kwargs),
            timeout=self._rtu_timeout(),
        )

    def _device_id(self) -> int:
        try:
            return max(1, int(self.config.connection_params.get("device_id", 1)))
        except (TypeError, ValueError):
            return 1

    @classmethod
    def get_capabilities(cls) -> dict[str, Any]:
        """Return modbus plugin capabilities."""
        capabilities = super().get_capabilities()
        capabilities.update({
            "supported_commands": ["set_coil", "set_valve"],
            "valve_mapping": {
                "valve-1": 0, "valve-2": 1, "valve-3": 2, "valve-4": 3,
                "valve-5": 4, "valve-6": 5, "valve-7": 6, "valve-8": 7,
                "valve-nc": 0, "valve-sc": 1, "valve-wc": 2,
            },
            "configuration_schema": {
                "connection_type": {
                    "type": "string",
                    "enum": ["modbus-rtu", "modbus-tcp"],
                    "default": "modbus-rtu",
                },
                "connection_params": {
                    "type": "object",
                    "properties": {
                        "serial_port": {"type": "string"},
                        "baudrate": {"type": "integer", "default": 19200},
                        "parity": {"type": "string", "enum": ["N", "E", "O"], "default": "N"},
                        "device_id": {"type": "integer", "default": 1, "minimum": 1},
                        "host": {"type": "string"},
                        "port": {"type": "integer", "default": 502},
                    },
                },
            },
        })
        return capabilities
