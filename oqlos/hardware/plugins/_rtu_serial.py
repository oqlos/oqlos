"""Shared RTU serial stale-handle detection and one-shot reconnect."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def serial_error_is_stale(exc: BaseException) -> bool:
    text = str(exc).lower()
    return (
        "errno 5" in text
        or "input/output error" in text
        or "errno 19" in text
        or "no such device" in text
    )


async def reopen_rtu_after_stale(plugin: Any, exc: BaseException, *, label: str) -> bool:
    """Close and reopen the RTU bus after USB tty re-enumeration (EIO)."""
    if not serial_error_is_stale(exc):
        return False
    try:
        await plugin.disconnect()
        connected = await plugin.connect()
        if connected:
            logger.info("%s: reopened RTU serial after stale handle", label)
        return bool(connected)
    except Exception as exc:
        logger.warning("%s: RTU reopen failed: %s", label, exc)
        return False


def rtu_timeout(config: Any) -> float:
    try:
        return max(0.1, float(config.timeout))
    except (TypeError, ValueError):
        return 2.0


def rtu_device_id(config: Any) -> int:
    try:
        return max(1, int(config.connection_params.get("device_id", 1)))
    except (TypeError, ValueError):
        return 1
