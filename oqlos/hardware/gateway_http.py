"""Shared httpx helpers for hardware gateway REST adapters."""

from __future__ import annotations

from typing import Any

import httpx

TIMEOUT = httpx.Timeout(5.0)


async def get_json(base_url: str, path: str) -> Any:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{base_url.rstrip('/')}{path}")
        resp.raise_for_status()
        return resp.json()


async def post_json(base_url: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(f"{base_url.rstrip('/')}{path}", json=payload)
        resp.raise_for_status()
        return resp.json()
