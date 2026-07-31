"""HUI hold / artificial-lung routes for the hardware API."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter

from oqlos.api.hardware_gateway import get_hardware_gateway
from oqlos.errors import OqlosError
from oqlos.errors.c2004_catalog_generated import CATALOG
from oqlos.hardware.hui_actions import (
    list_hui_actions,
    run_hui_valve_key,
    shutdown_all_hui_hardware,
    start_hui_artificial_lung,
    start_hui_hold,
    stop_hui_artificial_lung,
    stop_hui_hold,
)

router = APIRouter(tags=["hardware-hui"])

_SAFE_PLUGIN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


def _safe_unavailable_hardware_ids(payload: dict[str, Any]) -> list[str]:
    """Project only bounded plugin identifiers from an HUI failure payload."""
    candidates: list[Any] = []
    unavailable = payload.get("unavailable_hardware")
    if isinstance(unavailable, list):
        candidates.extend(
            item.get("plugin_id") if isinstance(item, dict) else item
            for item in unavailable
        )
    explicit = payload.get("unavailable_hardware_ids")
    if isinstance(explicit, list):
        candidates.extend(explicit)

    safe: list[str] = []
    for candidate in candidates:
        plugin_id = str(candidate or "").strip()
        if _SAFE_PLUGIN_ID_RE.fullmatch(plugin_id) and plugin_id not in safe:
            safe.append(plugin_id)
    return safe


def raise_if_hui_failed(
    payload: dict[str, Any], *, operation: str = "hui.action"
) -> None:
    if not payload.get("ok"):
        candidate = str(payload.get("error_code") or "")
        try:
            requested_status = int(payload.get("status_code") or 422)
        except (TypeError, ValueError):
            requested_status = 422
        if candidate in CATALOG:
            public_code = candidate
        elif requested_status == 503:
            public_code = "C2004-HW-0012"
        else:
            public_code = "C2004-DATA-0002"
        entry = CATALOG[public_code]
        issue_code = (
            "api_diagnostic_command_invalid"
            if entry.domain == "data"
            else "config_unavailable"
        )
        unavailable_hardware_ids = _safe_unavailable_hardware_ids(payload)
        safe_message = None
        detail: dict[str, Any] = {
            "architecture": "SOA",
            "layer": "firmware",
            "component": "hardware-hui",
            "stage": "action.execute",
            "problem_source": "hardware-action",
            "operation_id": operation[:128],
            "safe_to_retry": bool(payload.get("safe_to_retry", False)),
        }
        if unavailable_hardware_ids:
            names = ", ".join(unavailable_hardware_ids)
            safe_message = f"Required hardware unavailable: {names}"
            detail.update(
                {
                    "peripheral_id": unavailable_hardware_ids[0],
                    "unavailable_hardware_ids": unavailable_hardware_ids,
                    "failure_reason": safe_message,
                    "failure_codes": [
                        f"{plugin_id}-inactive"
                        for plugin_id in unavailable_hardware_ids
                    ],
                }
            )
        raise OqlosError(
            code=issue_code,
            public_code=public_code,
            status_code=entry.http_status,
            message=safe_message,
            detail=detail,
        )


async def start_hui_action(action: Any, *args: Any) -> dict[str, Any]:
    payload = await action(get_hardware_gateway(), *args)
    raise_if_hui_failed(payload, operation=f"hui.{getattr(action, '__name__', 'action')}")
    return payload


@router.get("/hui/actions")
async def hui_actions() -> dict[str, Any]:
    """Return OqlOS-owned HUI action recipes."""
    return list_hui_actions()


@router.post("/hui/shutdown", summary="Stop HUI pump/valve actions using the canonical OqlOS recipe")
async def hui_shutdown() -> dict[str, Any]:
    return await shutdown_all_hui_hardware(get_hardware_gateway())


@router.post("/hui/hold/{key}/start", summary="Start a named HUI hold action")
async def hui_hold_start(key: str) -> dict[str, Any]:
    return await start_hui_action(start_hui_hold, key)


@router.post("/hui/hold/{key}/stop", summary="Stop a named HUI hold action and return hardware to a safe state")
async def hui_hold_stop(key: str) -> dict[str, Any]:
    # Same fail-fast HTTP mapping as start (503 + C2004-HW-0012 when plugins down).
    return await start_hui_action(stop_hui_hold, key)


@router.post("/hui/valve/{key}", summary="Run a named HUI valve toggle (WC press/bleed)")
async def hui_valve_key(key: str) -> dict[str, Any]:
    return await start_hui_action(run_hui_valve_key, key)


@router.post("/hui/al/start", summary="Start the HUI artificial-lung action")
async def hui_al_start() -> dict[str, Any]:
    return await start_hui_action(start_hui_artificial_lung)


@router.post("/hui/al/stop", summary="Stop the HUI artificial-lung action")
async def hui_al_stop() -> dict[str, Any]:
    return await start_hui_action(stop_hui_artificial_lung)
