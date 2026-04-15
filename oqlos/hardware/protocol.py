"""
oqlos.hardware.protocol — Core abstraction for hardware protocols.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any


class ProtocolType(Enum):
    """Supported hardware communication protocols."""
    MODBUS_RTU = "modbus_rtu"
    HTTP_BRIDGE = "http_bridge"
    I2C_DIRECT = "i2c_direct"
    SPI_DIRECT = "spi_direct"
    GPIO_DIRECT = "gpio_direct"
    CAN_BUS = "can_bus"
    MQTT = "mqtt"
    OPC_UA = "opc_ua"


class HardwareProtocol(ABC):
    """
    Base class for all hardware drivers.
    
    A driver must implement basic read/write/connect/discover operations.
    """
    protocol_type: ProtocolType

    @abstractmethod
    async def connect(self, config: dict[str, Any]) -> bool:
        """Establish connection to the hardware."""
        ...

    @abstractmethod
    async def read(self, address: str, **kwargs: Any) -> Any:
        """Read a value from the hardware at specified address/register."""
        ...

    @abstractmethod
    async def write(self, address: str, value: Any, **kwargs: Any) -> bool:
        """Write a value to the hardware at specified address/register."""
        ...

    @abstractmethod
    async def discover(self) -> list[dict[str, Any]]:
        """Discover connected devices/peripherals on this protocol."""
        ...

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Perform a quick health check on the connection/hardware."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection to the hardware."""
        ...
