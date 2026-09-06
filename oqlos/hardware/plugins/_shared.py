"""Shared helpers for HTTP-bridge hardware plugins (motor, lung, piadc)."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from oqlos.errors.c2004_catalog_generated import CATALOG

from .base import PluginHealth, PluginStatus

logger = logging.getLogger(__name__)

PLUGIN_OPERATION_ERRORS = (OSError, RuntimeError, ValueError, httpx.HTTPError)
PLUGIN_PAYLOAD_ERRORS = (TypeError, ValueError)


def hardware_failure_payload(code: str, *, component: str, **details: Any) -> dict[str, Any]:
    """Attach validated failure identity to hardware diagnostic evidence."""
    if code not in CATALOG:
        raise ValueError(f"Unknown hardware failure code: {code}")
    return {
        **details,
        "ok": False,
        "success": False,
        "code": code,
        "error_code": code,
        "component": component,
    }


def plugin_operation_failure(
    component: str,
    reason: str,
    *,
    status_code: int = 503,
) -> dict[str, Any]:
    """Return a stable internal failure envelope for a hardware plugin."""
    error_code = "C2004-DATA-0002" if status_code == 422 else "C2004-HW-0012"
    return {
        "success": False,
        "error": "Hardware plugin operation failed",
        "reason": reason,
        "status_code": status_code,
        "code": error_code,
        "error_code": error_code,
        "architecture": "SOA",
        "component": component,
        "stage": "adapter.execute",
    }


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
