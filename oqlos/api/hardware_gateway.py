"""Shared HardwareGateway handle for hardware API route modules."""

from __future__ import annotations

from typing import Any

_gateway: Any | None = None


def set_hardware_gateway(gw: Any) -> None:
    global _gateway
    _gateway = gw


def get_hardware_gateway() -> Any:
    if _gateway is None:
        raise RuntimeError("HardwareGateway not initialised")
    return _gateway


def try_get_hardware_gateway() -> Any | None:
    return _gateway
