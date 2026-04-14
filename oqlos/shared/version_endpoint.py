"""Shared helpers for exposing service version endpoints.

Provides a small, consistent JSON payload for version endpoints across
backend, firmware, and any other FastAPI service in this repository.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter


def build_version_payload(
    service_name: str,
    version: str,
    *,
    endpoint: str = "/version",
    source: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a canonical JSON payload for a version endpoint."""

    payload: dict[str, Any] = {
        "status": "ok",
        "service": service_name,
        "version": version,
        "endpoint": endpoint,
    }
    if source:
        payload["source"] = source
    if extra:
        payload.update(dict(extra))
    return payload


def create_version_router(
    *,
    service_name: str,
    version: str,
    prefix: str = "",
    tags: list[str] | None = None,
    endpoint: str = "/version",
    public_endpoint: str | None = None,
    source: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> APIRouter:
    """Create a FastAPI router that exposes a single `/version` endpoint."""

    router = APIRouter(prefix=prefix, tags=tags or ["version"])

    @router.get(endpoint)
    async def version_info() -> dict[str, Any]:
        return build_version_payload(
            service_name,
            version,
            endpoint=public_endpoint or (f"{prefix.rstrip('/')}{endpoint}" if prefix else endpoint),
            source=source,
            extra=extra,
        )

    return router


__all__ = ["build_version_payload", "create_version_router"]
