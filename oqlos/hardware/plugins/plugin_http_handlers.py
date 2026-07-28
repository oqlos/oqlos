"""Shared simple HTTP command helpers for hardware plugins (no timing metadata)."""

from __future__ import annotations

from typing import Any


_UPSTREAM_ERROR_FIELDS = (
    "type",
    "title",
    "status",
    "detail",
    "code",
    "error_code",
    "legacy_error_code",
    "domain",
    "severity",
    "retryable",
    "architecture",
    "component",
    "stage",
    "correlation_id",
)


def _response_payload(resp: Any) -> Any:
    try:
        return resp.json()
    except Exception:
        return None


def _command_result(resp: Any) -> dict[str, Any]:
    payload = _response_payload(resp)
    if resp.status_code < 300:
        return {"success": True, "data": payload}

    upstream = payload if isinstance(payload, dict) else {}
    detail = upstream.get("detail") or upstream.get("error") or f"HTTP {resp.status_code}"
    result: dict[str, Any] = {
        "success": False,
        "error": str(detail),
        "status_code": resp.status_code,
    }
    for field in _UPSTREAM_ERROR_FIELDS:
        if field in upstream:
            result[field] = upstream[field]
    if upstream:
        result["upstream"] = upstream
    return result


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
    return _command_result(resp)


async def http_get_command(client: Any, base_url: str, path: str) -> dict[str, Any]:
    """GET from a plugin HTTP API and return ``{success, data|error}``."""
    url = f"{base_url.rstrip('/')}{path}"
    resp = await client.get(url)
    return _command_result(resp)
