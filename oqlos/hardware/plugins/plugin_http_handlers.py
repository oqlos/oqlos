"""Shared simple HTTP command helpers for hardware plugins (no timing metadata)."""

from __future__ import annotations

from typing import Any


async def http_post_command(
    client: Any,
    base_url: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """POST to a plugin HTTP API and return ``{success, data|error}``."""
    url = f"{base_url.rstrip('/')}{path}"
    if json_body is None:
        resp = await client.post(url)
    else:
        resp = await client.post(url, json=json_body)
    if resp.status_code < 300:
        return {"success": True, "data": resp.json()}
    return {"success": False, "error": f"HTTP {resp.status_code}"}


async def http_get_command(client: Any, base_url: str, path: str) -> dict[str, Any]:
    """GET from a plugin HTTP API and return ``{success, data|error}``."""
    url = f"{base_url.rstrip('/')}{path}"
    resp = await client.get(url)
    if resp.status_code < 300:
        return {"success": True, "data": resp.json()}
    return {"success": False, "error": f"HTTP {resp.status_code}"}
