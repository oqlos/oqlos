"""
oqlos.hardware.drivers.spi — SPI protocol driver for OqlOS HAL.
"""

from __future__ import annotations

import logging
from typing import Any

from oqlos.hardware.protocol import HardwareProtocol, ProtocolType
from oqlos.hardware.registry import DriverRegistry

try:
    import spidev
except ImportError:
    spidev = None


@DriverRegistry.register(ProtocolType.SPI_DIRECT)
class SpiDriver(HardwareProtocol):
    """
    SPI driver for HAL.
    Address format: "bus.device" (e.g. "0.0")
    """
    protocol_type = ProtocolType.SPI_DIRECT

    def __init__(self):
        self.spi = None
        self.bus = 0
        self.device = 0
        self.speed = 500000
        self.mode = 0

    async def connect(self, config: dict[str, Any]) -> bool:
        """Initialize SPI bus."""
        self.bus = config.get("bus", 0)
        self.device = config.get("device", 0)
        self.speed = config.get("speed", 500000)
        self.mode = config.get("mode", 0)

        if spidev is None:
            logging.warning("spidev not installed, SPI will run in simulation mode")
            return True

        try:
            self.spi = spidev.SpiDev()
            self.spi.open(self.bus, self.device)
            self.spi.max_speed_hz = self.speed
            self.spi.mode = self.mode
            return True
        except Exception as e:
            logging.error(f"SPI connection failed: {e}")
            return False

    async def read(self, address: str, **kwargs: Any) -> Any:
        """
        Read bytes from SPI.
        address: length of bytes to read (as string) or command byte.
        """
        length = kwargs.get("length", 1)
        if self.spi:
            return self.spi.readbytes(length)
        return [0] * length # Sim

    async def write(self, address: str, value: Any, **kwargs: Any) -> bool:
        """Write bytes to SPI."""
        if not isinstance(value, list):
            value = [value]
            
        if self.spi:
            try:
                self.spi.writebytes(value)
                return True
            except Exception as e:
                logging.error(f"SPI write failed: {e}")
                return False
        return True # Sim

    async def discover(self) -> list[dict[str, Any]]:
        return []

    async def health_check(self) -> dict[str, Any]:
        return {
            "status": "ok" if (self.spi or spidev is None) else "failed",
            "bus": self.bus,
            "device": self.device
        }

    async def disconnect(self) -> None:
        if self.spi:
            self.spi.close()
            self.spi = None
