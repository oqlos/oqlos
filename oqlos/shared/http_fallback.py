"""Narrow HTTP fallback helper for optional backend data sources."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeVar

import httpx

T = TypeVar("T")


async def fetch_first_json(
    sources: Sequence[str],
    normalize: Callable[[object], T | None],
    *,
    timeout_seconds: float,
) -> T | None:
    """Return the first accepted JSON payload from a list of optional sources.

    Network/status failures and malformed JSON are expected failover signals.
    Programming errors in the client or normalizer intentionally propagate to
    the application's sanitized unexpected-error boundary.
    """
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        for source in sources:
            try:
                response = await client.get(source)
                if not response.is_success:
                    continue
                payload = response.json()
            except (httpx.HTTPError, ValueError):
                continue
            normalized = normalize(payload)
            if normalized is not None:
                return normalized
    return None


__all__ = ["fetch_first_json"]
