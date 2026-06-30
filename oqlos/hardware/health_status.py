"""Shared hardware health status normalization."""

from __future__ import annotations

from typing import Any


def health_status_is_ok(raw_status: Any) -> bool:
    """Normalize old gateway string health and plugin-gateway dict health."""
    if isinstance(raw_status, dict):
        status = str(raw_status.get("status", "")).lower()
        compatible = raw_status.get("compatible")
        return status in {"ok", "connected"} and compatible is not False

    status = str(raw_status).lower()
    if not status:
        return False
    if status == "ok" or status.startswith("ok "):
        return True
    if status in {"connected", "healthy", "ready"}:
        return True
    if status.startswith(("connected ", "healthy ", "ready ")):
        return True
    if "error" in status or "offline" in status or "no-access" in status:
        return False
    return False
