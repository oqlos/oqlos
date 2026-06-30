"""Shared HTTP/CLI helpers for DRI0050 motor plugin command handlers."""

from __future__ import annotations

import asyncio
import subprocess
import time
from collections.abc import Callable
from typing import Any


async def motor_http_request(
    client: Any,
    base_url: str,
    *,
    method: str,
    path: str,
    start_time: float,
    json_body: dict[str, Any] | None = None,
    map_data: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Execute an HTTP motor API call and wrap the JSON response."""
    url = f"{base_url.rstrip('/')}{path}"
    if method.upper() == "GET":
        resp = await client.get(url)
    elif json_body is None:
        resp = await client.post(url)
    else:
        resp = await client.post(url, json=json_body)
    if resp.status_code < 300:
        data = resp.json()
        duration_ms = (time.monotonic() - start_time) * 1000
        return {
            "success": True,
            "data": {
                **map_data(data),
                "duration_ms": duration_ms,
                "timestamp": time.time(),
            },
        }
    return {"success": False, "error": f"HTTP {resp.status_code}"}


async def motor_cli_command(
    cmd_args: list[str],
    *,
    timeout: float,
    start_time: float,
    success_payload: dict[str, Any],
) -> dict[str, Any]:
    """Run a motor CLI subprocess and return a standardized plugin result."""
    proc = await asyncio.create_subprocess_exec(
        *cmd_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    duration_ms = (time.monotonic() - start_time) * 1000
    if proc.returncode == 0:
        payload = dict(success_payload)
        payload["duration_ms"] = duration_ms
        payload["timestamp"] = time.time()
        stdout_text = stdout.decode().strip()
        if stdout_text:
            payload["stdout"] = stdout_text
        return {"success": True, "data": payload}
    return {"success": False, "error": stderr.decode().strip()}
