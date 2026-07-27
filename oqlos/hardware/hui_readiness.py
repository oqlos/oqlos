"""Shared fail-fast readiness checks for HUI hardware actions."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any


async def required_plugins_failure(
    gateway: Any,
    plugin_ids: Iterable[str],
    *,
    command: str,
    key: str | None = None,
) -> dict[str, Any] | None:
    """Return a structured failure before an HUI action touches hardware."""
    required = tuple(dict.fromkeys(str(plugin_id).strip() for plugin_id in plugin_ids if plugin_id))
    if not required or not getattr(gateway, "is_real", False):
        return None

    readiness = getattr(gateway, "plugin_readiness", None)
    if not callable(readiness):
        return None

    # Hardware health probes may each consume their transport timeout. Run the
    # independent checks together so a 5 s Process URI does not turn two clear
    # device failures into an opaque gateway timeout.
    checks = list(await asyncio.gather(*(readiness(plugin_id) for plugin_id in required)))
    unavailable = [check for check in checks if not check.get("ok")]
    if not unavailable:
        return None

    names = ", ".join(str(check.get("plugin_id") or "unknown") for check in unavailable)
    payload: dict[str, Any] = {
        "ok": False,
        "command": command,
        "error": f"Required hardware unavailable: {names}",
        "error_code": "C2004-HW-0012",
        "status_code": 503,
        "required_hardware": list(required),
        "unavailable_hardware": unavailable,
        "operations": [],
        "safe_to_retry": False,
    }
    if key is not None:
        payload["key"] = key
    return payload
