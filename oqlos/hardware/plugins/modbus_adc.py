"""
Modbus ADC plugin - Waveshare Modbus RTU Analog Input 8CH integration.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .base import HardwarePlugin, PeripheralConfig, PluginConfig, PluginHealth, PluginStatus

logger = logging.getLogger(__name__)

_SENSOR_CHANNEL_ALIASES: dict[str, int] = {
    "ai01": 0,
    "ai1": 0,
    "nc-sensor": 0,
    "nc sensor": 0,
    "cisnienie-nc": 0,
    "ciśnienie-nc": 0,
    "nadcisnienie": 0,
    "nadciśnienie": 0,
    "pressure": 0,
    "pressure-sensor": 0,
    "ai02": 1,
    "ai2": 1,
    "sc-sensor": 1,
    "sc sensor": 1,
    "cisnienie-sc": 1,
    "ciśnienie-sc": 1,
    "ai03": 2,
    "ai3": 2,
    "wc-sensor": 2,
    "wc sensor": 2,
    "cisnienie-wc": 2,
    "ciśnienie-wc": 2,
    "ai04": 3,
    "ai4": 3,
    "spare": 3,
    "ai05": 4,
    "ai5": 4,
    "ai06": 5,
    "ai6": 5,
    "ai07": 6,
    "ai7": 6,
    "ai08": 7,
    "ai8": 7,
}

# Semantic aliases used in scenarios and shell diagnostics.
# IPx = input pressure x, IVx = input voltage x, IAx = input current x.
for idx in range(8):
    ch = idx
    n = idx + 1
    _SENSOR_CHANNEL_ALIASES[f"ip{n}"] = ch
    _SENSOR_CHANNEL_ALIASES[f"iv{n}"] = ch
    _SENSOR_CHANNEL_ALIASES[f"ia{n}"] = ch
    _SENSOR_CHANNEL_ALIASES[f"input-pressure-{n}"] = ch
    _SENSOR_CHANNEL_ALIASES[f"input-voltage-{n}"] = ch
    _SENSOR_CHANNEL_ALIASES[f"input-current-{n}"] = ch


def _resolve_channel(raw: Any) -> int | None:
    sensor_key = str(raw).strip()
    if sensor_key in {str(idx) for idx in range(8)}:
        return int(sensor_key)

    normalized_key = sensor_key.lower().replace("_", "-")
    return _SENSOR_CHANNEL_ALIASES.get(normalized_key)


def _modbus_error(result: Any) -> bool:
    is_error = getattr(result, "isError", None)
    return bool(is_error()) if callable(is_error) else False


class ModbusAdcPlugin(HardwarePlugin):
    """
    Plugin for Waveshare Modbus RTU Analog Input 8CH.

    The module exposes AI1-AI8 through input registers 0x0000-0x0007
    using Modbus function 04. Returned register values are passed through
    the optional per-channel conversion configured in oqlos.yaml.
    """

    PLUGIN_ID = "modbus-adc"
    PLUGIN_NAME = "Waveshare Modbus RTU Analog Input 8CH"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_DESCRIPTION = "8-channel Modbus RTU analog input module for pressure sensors"
    REQUIRED_PYTHON_PACKAGES = ["pymodbus"]
    SUPPORTED_PROTOCOLS = ["modbus-rtu"]

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self._client: Any = None
        self._bus: Any = None

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        if self.config.connection_type != "modbus-rtu":
            errors.append("modbus-adc supports modbus-rtu connection type")

        serial_port = self.config.connection_params.get("serial_port")
        if not serial_port:
            errors.append("serial_port is required in connection_params for modbus-adc")

        baudrate = self.config.connection_params.get("baudrate", 9600)
        if not isinstance(baudrate, int) or baudrate <= 0:
            errors.append("baudrate must be a positive integer")

        parity = self.config.connection_params.get("parity", "N")
        if parity not in ["N", "E", "O"]:
            errors.append("parity must be N, E, or O")

        for key in ("device_id", "read_count"):
            value = self.config.connection_params.get(key, 1)
            if not isinstance(value, int) or value <= 0:
                errors.append(f"{key} must be a positive integer")

        read_address = self.config.connection_params.get("read_address", 0)
        if not isinstance(read_address, int) or read_address < 0:
            errors.append("read_address must be a non-negative integer")

        read_count = self._read_count()
        if read_count > 8:
            errors.append("read_count must not exceed the 8 analog input channels")

        return errors

    async def connect(self) -> bool:
        try:
            try:
                from pimodbus.client import get_rtu_bus
                from pimodbus.config import RtuBusSettings
            except ImportError:
                logger.error("pymodbus not installed for modbus-adc")
                self._status = PluginStatus.INCOMPATIBLE
                return False

            serial_port = self.config.connection_params.get("serial_port", "/dev/ttyUSB0")
            baudrate = self.config.connection_params.get("baudrate", 9600)
            parity = self.config.connection_params.get("parity", "N")
            settings = RtuBusSettings(
                serial_port=serial_port,
                baudrate=baudrate,
                parity=parity,
                timeout=self.config.timeout,
            )
            self._bus = get_rtu_bus(settings)
            if await self._bus.connect():
                self._status = PluginStatus.CONNECTED
                logger.info("Connected to modbus-adc at %s@%s 8%s1", serial_port, baudrate, parity)
                return True

            self._status = PluginStatus.ERROR
            logger.error("Failed to connect to modbus-adc at %s", serial_port)
            return False
        except Exception as exc:
            self._status = PluginStatus.ERROR
            logger.error("Failed to connect to modbus-adc: %s", exc)
            return False

    async def disconnect(self) -> None:
        if self._bus:
            await self._bus.close()
            self._bus = None
        if self._client:
            self._client.close()
            self._client = None
        self._status = PluginStatus.CONFIGURED
        logger.info("Disconnected from modbus-adc")

    async def health_check(self) -> PluginHealth:
        if not self._client and not self._bus:
            return PluginHealth(
                status=PluginStatus.ERROR,
                message="Not connected to Modbus ADC",
                compatible=False,
            )

        try:
            registers = await self._read_registers()
            return PluginHealth(
                status=PluginStatus.CONNECTED,
                message="Modbus ADC is healthy",
                details={
                    "mode": "rtu",
                    "serial_port": self.config.connection_params.get("serial_port"),
                    "baudrate": self.config.connection_params.get("baudrate", 9600),
                    "parity": self.config.connection_params.get("parity", "N"),
                    "device_id": self._device_id(),
                    "read_address": self._read_address(),
                    "read_count": self._read_count(),
                    "registers": registers,
                },
                compatible=True,
                version=self.PLUGIN_VERSION,
            )
        except asyncio.TimeoutError:
            return PluginHealth(
                status=PluginStatus.ERROR,
                message=f"Modbus ADC read_input_registers timed out after {self._rtu_timeout():.1f}s",
                compatible=False,
            )
        except Exception as exc:
            return PluginHealth(
                status=PluginStatus.ERROR,
                message=f"Health check exception: {exc}",
                compatible=False,
            )

    async def execute_command(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self._client and not self._bus:
            return {"success": False, "error": "Not connected to Modbus ADC"}

        try:
            if command == "read_all":
                registers = await self._read_registers()
                return {
                    "success": True,
                    "data": {
                        "registers": registers,
                        "channels": self._format_channels(registers),
                    },
                }

            if command in {"read_channel", "read_sensor"}:
                raw_channel = params.get("channel", params.get("sensor_id", "ai01"))
                channel = _resolve_channel(raw_channel)
                if channel is None:
                    return {"success": False, "error": f"Unknown sensor/channel: {raw_channel}"}
                registers = await self._read_registers()
                if channel >= len(registers):
                    return {
                        "success": False,
                        "error": f"Channel {channel} is outside returned register range 0-{len(registers) - 1}",
                    }
                reading = self._format_channel(channel, registers[channel])
                if command == "read_sensor":
                    return {"success": True, "data": reading["value"], "details": reading}
                return {"success": True, "data": reading}

            return {"success": False, "error": f"Unknown command: {command}"}
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Modbus ADC read_input_registers timed out after {self._rtu_timeout():.1f}s"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def _read_registers(self) -> list[int]:
        if self._bus is not None:
            result = await self._bus.read_input_registers(
                address=self._read_address(),
                count=self._read_count(),
                device_id=self._device_id(),
                timeout=self._rtu_timeout(),
            )
        else:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    self._client.read_input_registers,
                    address=self._read_address(),
                    count=self._read_count(),
                    device_id=self._device_id(),
                ),
                timeout=self._rtu_timeout(),
            )
        if not result or _modbus_error(result):
            raise RuntimeError(f"Modbus ADC read_input_registers failed: {result}")
        registers = list(getattr(result, "registers", []) or [])
        if not registers:
            raise RuntimeError("Modbus ADC returned no input registers")
        return registers

    def _format_channels(self, registers: list[int]) -> dict[str, dict[str, Any]]:
        return {f"ai{idx + 1:02d}": self._format_channel(idx, raw) for idx, raw in enumerate(registers)}

    def _format_channel(self, channel: int, raw: int) -> dict[str, Any]:
        peripheral = self._peripheral_for_channel(channel)
        value = peripheral.convert_value(float(raw)) if peripheral else float(raw)
        unit = peripheral.scale.unit if peripheral else self.config.connection_params.get("unit", "raw")
        return {
            "channel": channel,
            "sensor_id": f"ai{channel + 1:02d}",
            "raw": raw,
            "value": value,
            "unit": unit,
        }

    def _peripheral_for_channel(self, channel: int) -> PeripheralConfig | None:
        keys = (
            f"ai{channel + 1:02d}",
            f"ai{channel + 1}",
            f"channel-{channel + 1}",
            f"channel_{channel + 1}",
        )
        for key in keys:
            peripheral = self.config.peripherals.get(key)
            if peripheral:
                return peripheral
        return None

    def _rtu_timeout(self) -> float:
        try:
            return max(0.1, float(self.config.timeout))
        except (TypeError, ValueError):
            return 2.0

    def _device_id(self) -> int:
        try:
            return max(1, int(self.config.connection_params.get("device_id", 1)))
        except (TypeError, ValueError):
            return 1

    def _read_address(self) -> int:
        try:
            return max(0, int(self.config.connection_params.get("read_address", 0)))
        except (TypeError, ValueError):
            return 0

    def _read_count(self) -> int:
        try:
            return max(1, int(self.config.connection_params.get("read_count", 8)))
        except (TypeError, ValueError):
            return 8

    @classmethod
    def get_capabilities(cls) -> dict[str, Any]:
        capabilities = super().get_capabilities()
        capabilities.update({
            "supported_commands": ["read_all", "read_channel", "read_sensor"],
            "supported_sensors": [
                "AI01",
                "AI02",
                "AI03",
                "AI04",
                "AI05",
                "AI06",
                "AI07",
                "AI08",
                "nc-sensor",
                "sc-sensor",
                "wc-sensor",
                "pressure-sensor",
            ],
            "channels": {str(idx): f"AI{idx + 1}" for idx in range(8)},
            "configuration_schema": {
                "connection_type": {"type": "string", "enum": ["modbus-rtu"], "default": "modbus-rtu"},
                "connection_params": {
                    "type": "object",
                    "properties": {
                        "serial_port": {"type": "string"},
                        "baudrate": {"type": "integer", "default": 9600},
                        "parity": {"type": "string", "enum": ["N", "E", "O"], "default": "N"},
                        "device_id": {"type": "integer", "default": 1, "minimum": 1},
                        "read_address": {"type": "integer", "default": 0, "minimum": 0},
                        "read_count": {"type": "integer", "default": 8, "minimum": 1, "maximum": 8},
                    },
                    "required": ["serial_port"],
                },
            },
        })
        return capabilities
