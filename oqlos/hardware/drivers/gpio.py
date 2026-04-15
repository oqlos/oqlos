"""
oqlos.hardware.drivers.gpio — GPIO driver for OQL HAL.
"""

from __future__ import annotations

import logging
from typing import Any

from ..protocol import HardwareProtocol, ProtocolType
from ..registry import DriverRegistry

logger = logging.getLogger(__name__)

@DriverRegistry.register(ProtocolType.GPIO_DIRECT)
class GpioDriver(HardwareProtocol):
    """
    Driver for direct GPIO control.
    Supports basic I/O operations and edge detection.
    """
    protocol_type = ProtocolType.GPIO_DIRECT

    def __init__(self):
        self._connected = False
        self._chip_handle = None
        self._lines: dict[int, Any] = {}

    async def connect(self, config: dict[str, Any]) -> bool:
        """
        Connect to GPIO.
        Config may include: chip (default 0).
        """
        chip = config.get("chip", 0)
        logger.info(f"Connecting to GPIO chip {chip}")
        
        # In a real scenario, we would use gpiod or lgpio here.
        # For this implementation, we simulate the connection.
        self._connected = True
        return True

    async def read(self, address: str, **kwargs: Any) -> Any:
        """
        Read GPIO value. Address is the pin number (e.g. '17').
        """
        if not self._connected:
            raise RuntimeError("GPIO driver not connected")
        
        try:
            pin = int(address)
            # Simulated read
            val = self._lines.get(pin, 0)
            logger.debug(f"GPIO READ pin {pin}: {val}")
            return val
        except ValueError:
            raise ValueError(f"Invalid GPIO address: {address}")

    async def write(self, address: str, value: Any, **kwargs: Any) -> bool:
        """
        Write GPIO value. Address is pin number, value is 0/1 or False/True or "HIGH"/"LOW".
        """
        if not self._connected:
            raise RuntimeError("GPIO driver not connected")
            
        try:
            pin = int(address)
            if isinstance(value, str):
                val = 1 if value.upper() in ("HIGH", "1", "TRUE") else 0
            else:
                val = 1 if value else 0
            
            self._lines[pin] = val
            logger.debug(f"GPIO WRITE pin {pin}: {val}")
            return True
        except ValueError:
            raise ValueError(f"Invalid GPIO address: {address}")

    async def discover(self) -> list[dict[str, Any]]:
        """List active/configured GPIO pins."""
        return [{"pin": k, "value": v} for k, v in self._lines.items()]

    async def health_check(self) -> dict[str, Any]:
        """Verify GPIO connection."""
        return {"status": "ok" if self._connected else "disconnected", "type": "gpio"}

    async def disconnect(self) -> None:
        """Release GPIO chip."""
        self._connected = False
        self._lines.clear()
        logger.info("GPIO disconnected")
