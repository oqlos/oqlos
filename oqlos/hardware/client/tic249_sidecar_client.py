from __future__ import annotations

import os
from typing import Any

import httpx

from oqlos.hardware.client.errors import HardwareProxyError
from oqlos.hardware.client.proxy import OqlosHardwareProxy
from oqlos.hardware.client.tic249_error_messages import command_failure, normalize_target_state

_LUNG_DISABLE_PATH = "/api/v1/hardware/lung/disable"
_RECIPROCATE_PAYLOAD_KEYS = frozenset(
    {
        "steps",
        "speed",
        "cycles",
        "pause",
        "direction",
        "start_direction",
        "limit_mode",
        "acceleration",
        "ramp_seconds",
        "ramp_time_sec",
        "ramp_time",
    }
)


def tic249_sidecar_base_urls() -> list[str]:
    """Candidate Tic sidecar bases (host, container, and explicit env)."""
    seen: set[str] = set()
    urls: list[str] = []
    for raw in (
        os.getenv("TIC249_DIRECT_API_BASE"),
        os.getenv("OQLOS_LUNG_MOTOR_URL"),
        os.getenv("LUNG_MOTOR_URL"),
        os.getenv("TIC249_URL"),
        "http://hw-tic249:5000",
        "http://127.0.0.1:8205",
        "http://localhost:8205",
        "http://host.docker.internal:8205",
    ):
        if not raw:
            continue
        base = str(raw).rstrip("/")
        if base in seen:
            continue
        seen.add(base)
        urls.append(base)
    return urls or ["http://127.0.0.1:8205"]


def tic249_sidecar_base_url() -> str:
    return tic249_sidecar_base_urls()[0]


def sidecar_reciprocate_preferred() -> bool:
    """Prefer hw-tic249 /api/reciprocate (real limit switches) over OqlOS plugin mock."""
    return os.getenv("TIC249_RECIPROCATE_VIA_SIDECAR", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


async def sidecar_reports_deenergized() -> bool:
    async with httpx.AsyncClient(timeout=3.0) as client:
        for base in tic249_sidecar_base_urls():
            try:
                resp = await client.get(f"{base}/api/status")
            except Exception:
                continue
            if resp.status_code >= 300:
                continue
            payload = resp.json() if resp.content else {}
            if isinstance(payload, dict) and payload.get("energized") is False:
                return True
    return False


async def attempt_reciprocate_via_sidecar(params: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """POST /api/reciprocate on Tic249 sidecar (rpi-motor-tic249 web_panel)."""
    payload = {k: v for k, v in params.items() if k in _RECIPROCATE_PAYLOAD_KEYS}
    async with httpx.AsyncClient(timeout=httpx.Timeout(8.0)) as client:
        for base in tic249_sidecar_base_urls():
            try:
                resp = await client.post(f"{base}/api/reciprocate", json=payload)
            except Exception:
                continue
            if resp.status_code >= 300:
                continue
            body = resp.json() if resp.content else {}
            if not isinstance(body, dict):
                continue
            if body.get("success") is False:
                continue
            return {**body, "success": True, "fallback": "tic249_sidecar_reciprocate", "base_url": base}, base
    return None, None


async def direct_sidecar_deenergize(command: str) -> dict[str, Any] | None:
    """De-energize via Tic sidecar when OqlOS plugin registry has no active instance."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        for base in tic249_sidecar_base_urls():
            try:
                resp = await client.post(f"{base}/api/energize", json={"enable": False})
            except Exception:
                continue
            if resp.status_code >= 300:
                continue
            payload = resp.json() if resp.content else {}
            if not isinstance(payload, dict):
                continue
            normalized = normalize_target_state(command, {**payload, "success": True, "data": payload})
            if command_failure(normalized) is not None:
                continue
            return {**normalized, "fallback": "tic249_sidecar_energize", "base_url": base}
    return None


async def lung_disable_fallback(hardware_proxy: OqlosHardwareProxy, command: str) -> dict[str, Any] | None:
    """Retry de-energize through the lung/disable route when plugin execute fails."""
    try:
        result = await hardware_proxy._proxy_oqlos_request("POST", _LUNG_DISABLE_PATH, payload=None)
    except HardwareProxyError:
        return None
    if not isinstance(result, dict):
        return None
    normalized = normalize_target_state(command, result)
    if command_failure(normalized) is not None:
        return None
    return {**normalized, "fallback": "lung_disable"}


def disable_success_response(
    command: str,
    fallback_result: dict[str, Any],
    fallback_name: str,
) -> dict[str, Any]:
    if fallback_name == "lung_disable":
        target_path = _LUNG_DISABLE_PATH
        target_params: dict[str, Any] = {}
    elif fallback_name == "tic249_sidecar_status":
        target_path = f"{tic249_sidecar_base_url()}/api/status"
        target_params = {}
    else:
        target_path = f"{tic249_sidecar_base_url()}/api/energize"
        target_params = {"enable": False}
    return {
        "ok": True,
        "peripheral_id": "motor-tic249",
        "command": command,
        "target": {"method": "POST", "path": target_path, "params": target_params},
        "result": fallback_result,
        "note": f"De-energize via {fallback_name} (plugin registry not required)",
    }


async def attempt_disable_deenergize(
    hardware_proxy: OqlosHardwareProxy,
    command: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Sidecar and lung/disable paths do not require an OqlOS plugin registry instance."""
    for fallback_name, attempt in (
        ("tic249_sidecar_energize", lambda: direct_sidecar_deenergize(command)),
        ("lung_disable", lambda: lung_disable_fallback(hardware_proxy, command)),
    ):
        result = await attempt()
        if result is not None:
            return result, fallback_name
    if await sidecar_reports_deenergized():
        return (
            {
                "success": True,
                "status": "de-energized",
                "idempotent_success": True,
                "fallback": "tic249_sidecar_status",
            },
            "tic249_sidecar_status",
        )
    return None, None
