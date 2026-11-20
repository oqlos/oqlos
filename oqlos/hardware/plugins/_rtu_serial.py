"""Shared RTU serial stale-handle detection and one-shot reconnect."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

DEFAULT_MODBUS_BAUD_RATE = 4_800
MODBUS_RTU_BITS_PER_CHAR = 11
MODBUS_HIGH_BAUD_THRESHOLD = 19_200
MODBUS_FIXED_T35_US = 1_750
MICROSECONDS_PER_SEC = 1_000_000

_T = TypeVar("_T")


def modbus_rtu_t35_us(baud_rate: int = DEFAULT_MODBUS_BAUD_RATE) -> int:
    """Return Modbus RTU t3.5 inter-frame turnaround delay in microseconds.

    Matches maskservice/boardnet-digital-twin#37:
    - 4800 baud -> 8021 us
    - 9600 baud -> 4011 us
    - 19200 baud -> 2006 us
    - >19200 baud -> fixed 1750 us
    """
    if isinstance(baud_rate, bool) or not isinstance(baud_rate, int) or baud_rate <= 0:
        raise ValueError("baud_rate must be a positive integer")
    if baud_rate > MODBUS_HIGH_BAUD_THRESHOLD:
        return MODBUS_FIXED_T35_US
    numerator = 7 * MODBUS_RTU_BITS_PER_CHAR * MICROSECONDS_PER_SEC
    denominator = 2 * baud_rate
    return (numerator + denominator - 1) // denominator


def modbus_rtu_t35_seconds(baud_rate: int = DEFAULT_MODBUS_BAUD_RATE) -> float:
    """Return Modbus RTU t3.5 turnaround delay in seconds."""
    return modbus_rtu_t35_us(baud_rate) / MICROSECONDS_PER_SEC


def rtu_baudrate(config: Any, default: int = DEFAULT_MODBUS_BAUD_RATE) -> int:
    raw = config.connection_params.get("baudrate", default)
    if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
        return default
    return raw


class RtuTurnaroundPacer:
    """Serializes RTU transactions and enforces baud-dependent t3.5 silence."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._lock = asyncio.Lock()
        self._clock = clock
        self._sleeper = sleeper
        self._last_finished_ts: float | None = None

    def reset(self) -> None:
        self._last_finished_ts = None

    async def run(self, baud_rate: int, op: Callable[[], Awaitable[_T]]) -> _T:
        min_gap_s = modbus_rtu_t35_seconds(baud_rate)
        async with self._lock:
            if self._last_finished_ts is not None:
                elapsed = self._clock() - self._last_finished_ts
                remaining = min_gap_s - elapsed
                if remaining > 0:
                    await self._sleeper(remaining)
            try:
                return await op()
            finally:
                self._last_finished_ts = self._clock()


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
