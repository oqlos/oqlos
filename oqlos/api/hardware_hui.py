"""HUI hold / artificial-lung routes for the hardware API."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter

from oqlos.api import hardware_platform as platform
from oqlos.api.hardware_gateway import get_hardware_gateway
from oqlos.api.hardware_hui_profile_source import router as hui_profile_source_router
from oqlos.api.hardware_identify import _analog_input_health
from oqlos.errors import OqlosError
from oqlos.errors.c2004_catalog_generated import CATALOG
from oqlos.hardware.hui_actions import (
    build_hui_readiness,
    list_hui_actions,
    run_hui_valve_key,
    shutdown_all_hui_hardware,
    start_hui_artificial_lung,
    start_hui_hold,
    stop_hui_artificial_lung,
    stop_hui_hold,
)

router = APIRouter(tags=["hardware-hui"])
router.include_router(hui_profile_source_router)

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


def _safe_action_progress(payload: dict[str, Any]) -> dict[str, Any]:
    """Project only bounded, non-secret shutdown progress into public errors."""
    projected: dict[str, Any] = {}
    status = str(payload.get("status") or "")
    if status in {"safe", "partial", "failed"}:
        projected["status"] = status
    allowed_fields = {
        "requested": {"pump_off", "valves_off", "motor_stop", "valve_close"},
        "executed": {"pump_off", "valves_off", "motor_stop", "valve_close"},
        "confirmed": {"pump_off", "valves_off", "motor_stopped", "valve_closed"},
    }
    for section, allowed_keys in allowed_fields.items():
        value = payload.get(section)
        if not isinstance(value, dict):
            continue
        safe_section: dict[str, Any] = {}
        for key in allowed_keys:
            item = value.get(key)
            if isinstance(item, bool):
                safe_section[key] = item
            elif isinstance(item, str) and _SAFE_PLUGIN_ID_RE.fullmatch(item):
                safe_section[key] = item
            elif isinstance(item, list):
                safe_section[key] = [
                    text
                    for candidate in item[:32]
                    if (text := str(candidate or "").strip())
                    and _SAFE_PLUGIN_ID_RE.fullmatch(text)
                ]
        if safe_section:
            projected[section] = safe_section
    return projected


def _hui_issue_code(*, domain: str, unavailable_ids: list[str]) -> str:
    """Map HUI failures to operator-facing issue codes (never YAML-load lies)."""
    if domain == "data":
        return "api_diagnostic_command_invalid"
    blob = " ".join(unavailable_ids).lower()
    if "modbus" in blob:
        return "hw_modbus_no_response"
    if "tic249" in blob:
        return "hw_tic249_sidecar_unreachable"
    if "dri0050" in blob:
        return "hw_dri0050_sidecar_unreachable"
    if any(token in blob for token in ("usb-adc", "dfr1184", "mcp2221")):
        return "hw_usb_adc_sidecar_unreachable"
    if unavailable_ids:
        # CODE_PATTERNS → adapter_<id>_health_not_ok summary (not config YAML).
        return f"adapter_{unavailable_ids[0]}_health_not_ok"
    return "identify_unavailable"


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
        unavailable_hardware_ids = _safe_unavailable_hardware_ids(payload)
        explicit_issue = str(payload.get("issue_code") or "").strip()
        issue_code = explicit_issue or _hui_issue_code(
            domain=entry.domain, unavailable_ids=unavailable_hardware_ids
        )
        # `error` may carry plugin/serial internals and never reaches the client.
        # An action that has a specific, operator-safe reason states it in
        # `public_message`; without it the generic hardware sentence is used, which
        # on the STOP path used to point at a device that was answering fine.
        safe_message = str(payload.get("public_message") or "").strip()[:256] or None
        detail: dict[str, Any] = {
            "architecture": "SOA",
            "layer": "firmware",
            "component": "hardware-hui",
            "stage": "action.execute",
            "problem_source": "hardware-action",
            "operation_id": operation[:128],
            "safe_to_retry": bool(payload.get("safe_to_retry", False)),
            "issue_code": issue_code,
        }
        if unavailable_hardware_ids:
            names = ", ".join(unavailable_hardware_ids)
            if safe_message is None:
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
        detail.update(_safe_action_progress(payload))
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


@router.get("/hui/readiness")
async def hui_readiness() -> dict[str, Any]:
    """Return a non-reconnecting HUI preflight, split into control and telemetry."""
    runtime_platform = platform._detect_runtime_platform()
    analog_health = await _analog_input_health(runtime_platform)
    return await build_hui_readiness(
        get_hardware_gateway(),
        analog_input_health=analog_health,
    )


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
