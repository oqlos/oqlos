"""Shared helpers for HTTP-bridge hardware plugins (motor, lung, piadc)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

from .base import PluginHealth, PluginStatus

logger = logging.getLogger(__name__)


async def http_health_check(
    client: httpx.AsyncClient,
    base_url: str,
    label: str,
) -> PluginHealth:
    """Shared HTTP health check — GET {base_url}/health."""
    resp = await client.get(f"{base_url}/health")
    if resp.status_code < 300:
        data = resp.json()
        return PluginHealth(
            status=PluginStatus.CONNECTED,
            message=f"{label} is healthy",
            details=data,
            compatible=True,
            version=data.get("version", "unknown"),
        )
    return PluginHealth(
        status=PluginStatus.ERROR,
        message=f"Health check failed: HTTP {resp.status_code}",
        compatible=False,
    )


def not_connected_health(label: str) -> PluginHealth:
    """Return error health when plugin has no active client."""
    return PluginHealth(
        status=PluginStatus.ERROR,
        message=f"Not connected to {label}",
        compatible=False,
    )


def health_check_exception(exc: Exception) -> PluginHealth:
    """Return error health for unexpected exceptions."""
    return PluginHealth(
        status=PluginStatus.ERROR,
        message=f"Health check exception: {exc}",
        compatible=False,
    )


async def http_disconnect(client: httpx.AsyncClient | None, label: str) -> None:
    """Close an httpx client (if open) and log disconnect."""
    if client:
        await client.aclose()
    logger.info(f"Disconnected from {label}")
