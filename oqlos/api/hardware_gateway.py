"""Shared HardwareGateway handle for hardware API route modules."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

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


async def snapshot_via_health(build_fn: Callable[[Any], Any]) -> Any:
    """Fetch gateway health, then build a report from it off the event loop."""
    health = await get_hardware_gateway().health()
    return await asyncio.to_thread(build_fn, health)


def is_plugin_compatible(health_entry: Any) -> bool:
    """Return True when plugin health confirms adapter is reachable and compatible."""
    return isinstance(health_entry, dict) and bool(health_entry.get("compatible"))
