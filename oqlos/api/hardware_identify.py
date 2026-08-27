"""Hardware health and identify HTTP routes."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Query

from oqlos.api import hardware_platform as platform
from oqlos.api import hardware_probe as hw_probe
from oqlos.api.hardware_gateway import get_hardware_gateway
from oqlos.api.hardware_registry import HARDWARE_REGISTRY
from oqlos.hardware.identify_enrichment import enrich_identify_payload
from oqlos.hardware.power_safety import sample_power_telemetry
from oqlos.hardware.usb_adc_stack import UsbAdcStackError, read_usb_adc_health

router = APIRouter(tags=["hardware-identify"])


async def _analog_input_health(runtime_platform: dict[str, Any]) -> dict[str, Any] | None:
    """Return dedicated ADC health when usb-adc-stack owns analog inputs."""
    if runtime_platform.get("analog_input_driver_role") != "usb-adc-stack":
        return None
    from oqlos.config import get_settings

    settings = get_settings()
    try:
        return await read_usb_adc_health(
            settings.usb_adc_stack_url,
            timeout_seconds=settings.usb_adc_timeout_seconds,
        )
    except UsbAdcStackError:
        return {
            "ok": False,
            "status": "unavailable",
            "message": "usb-adc-stack health endpoint is unavailable",
            "components": {},
        }


def _hardware_health_overall_ok(payload: dict[str, Any]) -> bool:
    """True when every enabled plugin entry in the health payload is compatible."""
    skip_keys = {
        "mode",
        "note",
        "platform",
        "modbus",
        "overall_ok",
        "degraded",
        "init_summary",
        "power",
        "errors",
    }
    for key, entry in payload.items():
        if key in skip_keys or not isinstance(entry, dict):
            continue
        if entry.get("status") == "disabled" and entry.get("required") is not True:
            continue
        if entry.get("compatible") is not True:
            return False
    return True


def _determine_scan_set(
    scan_mode: str, health: "dict[str, Any]"
) -> tuple["set[str]", bool, str]:
    """
    Compute the set of adapter IDs that need a live scan probe.
    Returns (scan_ids, skipped_owned_modbus, skip_reason).
    """
    scan_ids: set[str] = set()
    skipped_owned_modbus_probe = False
    scan_skip_reason = "plugin-health compatible" if scan_mode == "auto" else "scan=never"

    if scan_mode == "always":
        scan_ids = {hw["id"] for hw in HARDWARE_REGISTRY}
    elif scan_mode == "auto" and hw_probe._needs_live_scan(health):
        scan_ids = hw_probe._unhealthy_plugin_ids(health)

    for plugin_key in ("modbus-io", "modbus-adc"):
        plugin_health = health.get(plugin_key)
        if isinstance(plugin_health, dict) and hw_probe._modbus_health_is_no_response(plugin_health):
            skipped_owned_modbus_probe = plugin_key in scan_ids or skipped_owned_modbus_probe
            scan_ids.discard(plugin_key)

    if skipped_owned_modbus_probe:
        scan_skip_reason = "plugin owns Modbus serial port; skipped duplicate no-response probe"

    return scan_ids, skipped_owned_modbus_probe, scan_skip_reason


def _map_adapter_identify_status(
    hw: "dict[str, Any]",
    health: "dict[str, Any]",
    probes: "dict[str, Any]",
) -> "dict[str, Any]":
    """Build the adapter entry dict with status based on health and probe results."""
    hw_id = hw["id"]
    local_probe = probes.get(hw_id, {})
    health_entry = health.get(hw_id)
    entry = {**hw, "status": "offline", "probe": local_probe}

    if isinstance(health_entry, dict):
        entry["probe"] = {
            "connected": bool(health_entry.get("compatible")),
            "source": "plugin-health",
            "health": health_entry,
            "local_probe": local_probe,
        }
        if health_entry.get("compatible"):
            entry["status"] = "ok"
        elif health_entry.get("status") == "error":
            if hw_id in {"modbus-io", "modbus-adc"} and hw_probe._modbus_health_is_no_response(health_entry):
                entry["status"] = "adapter-only"
                entry["probe"]["diagnosis"] = (
                    "serial adapter is open in OqlOS, but the Modbus device did not answer"
                )
            else:
                entry["status"] = "no-access"
        else:
            entry["status"] = "offline"
    elif local_probe.get("connected"):
        if hw_id in {"modbus-io", "modbus-adc"} and not local_probe.get("modbus_device_responds", True):
            entry["status"] = "adapter-only"
        else:
            entry["status"] = "ok"
    elif local_probe.get("reason"):
        entry["status"] = "no-access"
    else:
        entry["status"] = "offline"

    return entry


@router.get("/health")
async def hardware_health(
    plugin_timeout_seconds: Annotated[
        float | None,
        Query(ge=0.1, le=10.0),
    ] = None,
):
    """Return connectivity status for all hardware services."""
    gateway = get_hardware_gateway()
    payload = (
        await gateway.health(timeout=plugin_timeout_seconds)
        if plugin_timeout_seconds is not None
        else await gateway.health()
    )
    if isinstance(payload, dict):
        power = await sample_power_telemetry()
        payload["power"] = power
        if power.get("errors"):
            payload["errors"] = list(power["errors"])
        payload["platform"] = platform._detect_runtime_platform()
        if payload.get("mode") == "real":
            overall_ok = _hardware_health_overall_ok(payload) and not bool(power.get("errors"))
            payload["overall_ok"] = overall_ok
            payload["degraded"] = not overall_ok
            if not overall_ok:
                payload["status"] = "degraded"
    return payload


@router.get("/identify")
async def hardware_identify(
    scan: str = Query(
        default="never",
        description="Scan mode: auto (scan only on failure), always (force live scan), never (skip live scan)",
    )
):
    """Return hardware identification with conditional live scanning for low latency."""
    scan_mode_raw = scan if isinstance(scan, str) else "never"
    scan_mode = (scan_mode_raw or "never").strip().lower()
    if scan_mode not in {"auto", "always", "never"}:
        scan_mode = "never"

    health = await get_hardware_gateway().health()
    runtime_platform = platform._detect_runtime_platform()
    analog_input_health = await _analog_input_health(runtime_platform)
    scan_ids, skipped_owned_modbus_probe, scan_skip_reason = _determine_scan_set(scan_mode, health)
    should_scan = bool(scan_ids)

    if should_scan:
        probes_task = asyncio.to_thread(hw_probe._probe_selected_hardware, scan_ids)
        diagnostics_task = asyncio.to_thread(hw_probe._collect_hardware_diagnostics)
        probes, diagnostics = await asyncio.gather(probes_task, diagnostics_task)
    else:
        probes = {}
        diagnostics = {"scan_skipped": True, "scan_skip_reason": scan_skip_reason}

    adapters = [_map_adapter_identify_status(hw, health, probes) for hw in HARDWARE_REGISTRY]

    mode = health.get("mode", "mock")
    payload = {
        "mode": mode,
        "platform": runtime_platform,
        "detected": sum(1 for a in adapters if a["status"] == "ok"),
        "total": len(adapters),
        "adapters": adapters,
        "diagnostics": {
            "health": health,
            "scan_mode": scan_mode,
            "scan_performed": should_scan,
            "modbus_preflight": hw_probe._modbus_preflight_report(),
            "modbus_repair": hw_probe._modbus_repair_guidance(health),
            **(
                {"analog_input_health": analog_input_health}
                if analog_input_health is not None
                else {}
            ),
            **diagnostics,
        },
    }
    return enrich_identify_payload(payload)
