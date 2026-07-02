"""Shared helpers for HTTP-bridge hardware plugins (motor, lung, piadc)."""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

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
    return _error_health(f"Not connected to {label}")


def health_check_exception(exc: Exception) -> PluginHealth:
    return _error_health(f"Health check exception: {exc}")


def _error_health(message: str) -> PluginHealth:
    return PluginHealth(
        status=PluginStatus.ERROR,
        message=message,
        compatible=False,
    )


async def http_disconnect(client: httpx.AsyncClient | None, label: str) -> None:
    """Close an httpx client (if open) and log disconnect."""
    if client:
        await client.aclose()
    logger.info(f"Disconnected from {label}")


async def disconnect_http_plugin(plugin: Any, label: str) -> None:
    """Close plugin._client, clear the reference, and mark plugin as CONFIGURED."""
    await http_disconnect(plugin._client, label)
    plugin._client = None
    plugin._status = PluginStatus.CONFIGURED
