"""USB enumeration and Pi diagnostics verbs for manage_ops."""

from __future__ import annotations

import asyncio
from typing import Any


async def usb_list(_a: dict[str, Any]) -> dict[str, Any]:
    """Enumerate USB devices on the node (runs in a thread; reads sysfs)."""
    from oqlos.hardware import usb_diagnostics as u

    devices = await asyncio.to_thread(u.list_usb_devices)
    return {"ok": True, "count": len(devices), "devices": devices}


async def pi_diagnostics(_a: dict[str, Any]) -> dict[str, Any]:
    """Raspberry Pi system diagnostics snapshot."""
    from oqlos.hardware import usb_diagnostics as u

    return await asyncio.to_thread(u.pi_system_diagnostics)


async def usb_reset(a: dict[str, Any]) -> dict[str, Any]:
    """Driver-level reset/re-enumeration of a USB device (best-effort; may need root)."""
    from oqlos.hardware import usb_diagnostics as u

    return await asyncio.to_thread(
        u.reset_usb_device,
        a.get("vendor_id"),
        a.get("product_id"),
        a.get("dev_node"),
    )
