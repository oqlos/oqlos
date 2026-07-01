"""
oqlos.hardware.registry — Driver registry for Hardware HAL.
"""

from __future__ import annotations

import logging
from typing import Type

from .protocol import HardwareProtocol, ProtocolType

logger = logging.getLogger(__name__)


class DriverRegistry:
    """ Registry for hardware drivers. Allows mapping ProtocolType to specific HardwareProtocol implementations. """
    _drivers: dict[ProtocolType, Type[HardwareProtocol]] = {}

    @classmethod
    def register(cls, protocol: ProtocolType):
        """
        Decorator to register a driver class for a specific protocol.
        
        Example:
            @DriverRegistry.register(ProtocolType.GPIO_DIRECT)
            class GpioDriver(HardwareProtocol): ...
        """
        def decorator(driver_class: Type[HardwareProtocol]):
            cls._drivers[protocol] = driver_class
            return driver_class
        return decorator

    @classmethod
    def create(cls, protocol: ProtocolType) -> HardwareProtocol:
        """
        Create an instance of a driver for the specified protocol.
        """
        driver_class = cls._drivers.get(protocol)
        if not driver_class:
            raise ValueError(f"No driver registered for protocol {protocol}")
        
        # We don't initialize here with config because initialization 
        # usually happens via .connect(config) in our HAL pattern.
        return driver_class()

    @classmethod
    def list_registered(cls) -> list[ProtocolType]:
        """List all registered protocol types."""
        return list(cls._drivers.keys())
