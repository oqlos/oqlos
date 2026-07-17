"""Deploy/update status for BoardNet operators."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Request

from oqlos.services.update_status import (
    build_update_status_payload,
    compute_git_drift,
    read_deploy_commit,
    read_update_progress,
)

router = APIRouter(tags=["update"])

UPDATE_PAGE = Path(__file__).resolve().parent / "static" / "update" / "index.html"


async def _probe_json(url: str, *, timeout: float = 5.0) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
        return {"status": "ok", "url": url, "payload": payload}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "url": url, "error": str(exc)}


async def _collect_health(base_url: str) -> dict[str, Any]:
    sidecars = {
        "dri0050": "http://127.0.0.1:8203/api/status",
        "tic249": "http://127.0.0.1:8205/api/status",
        "pirtc": "http://127.0.0.1:8125/api/status",
    }
    components = {
        "oqlos": await _probe_json(f"{base_url.rstrip('/')}/health"),
    }
    for name, url in sidecars.items():
        components[name] = await _probe_json(url, timeout=4.0)
    degraded = any(item.get("status") != "ok" for item in components.values())
    return {"status": "degraded" if degraded else "ok", "components": components}


async def _collect_hardware_summary(base_url: str) -> dict[str, Any]:
    result = await _probe_json(f"{base_url.rstrip('/')}/api/v1/hardware/health", timeout=8.0)
    if result.get("status") != "ok":
        return {"status": "error", "error": result.get("error")}
    payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
    summary = payload.get("init_summary") if isinstance(payload.get("init_summary"), dict) else {}
    return {
        "status": payload.get("status") or ("ok" if payload.get("overall_ok") else "degraded"),
        "mode": payload.get("mode"),
        "connected": len(summary.get("connected") or []),
        "failed": len(summary.get("failed") or []),
        "disabled": len(summary.get("disabled") or []),
    }


@router.get("/update/status")
async def get_update_status(request: Request) -> dict[str, Any]:
    base_url = str(request.base_url).rstrip("/")
    deploy = read_deploy_commit()
    update_progress = read_update_progress()
    git_drift = compute_git_drift(deploy.get("commit"))
    health = await _collect_health(base_url)
    hardware = await _collect_hardware_summary(base_url)
    return build_update_status_payload(
        deploy=deploy,
        update_progress=update_progress,
        git_drift=git_drift,
        health=health,
        hardware=hardware,
    )
