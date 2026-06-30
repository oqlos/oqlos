"""Analyze hardware identify payloads and plan best-effort auto-repair steps."""

from __future__ import annotations

from typing import Any

from oqlos.hardware.diagnosis import (
    is_stale_hardware_entry,
    is_stale_hardware_message,
    plugin_needs_repair as _oqlos_plugin_needs_repair,
)

_PLUGIN_IDS = ("modbus-io", "modbus-adc", "motor-dri0050", "motor-tic249")


def _health_map(identify: dict[str, Any]) -> dict[str, Any]:
    diagnostics = identify.get("diagnostics") if isinstance(identify, dict) else {}
    health = diagnostics.get("health") if isinstance(diagnostics, dict) else {}
    return health if isinstance(health, dict) else {}


def plugin_needs_repair(plugin_id: str, entry: dict[str, Any] | None) -> bool:
    if not isinstance(entry, dict):
        return False
    if _oqlos_plugin_needs_repair(plugin_id, entry):
        return True
    status = str(entry.get("status") or "").lower()
    message = str(entry.get("message") or "").lower()
    if plugin_id.startswith("modbus") and status == "adapter-only":
        return "healthy" not in message and "connected" not in message
    return False


def modbus_plugins_need_repair(identify: dict[str, Any] | None) -> bool:
    health = _health_map(identify or {})
    for key in ("modbus-io", "modbus-adc"):
        if plugin_needs_repair(key, health.get(key) if isinstance(health.get(key), dict) else {}):
            return True
    return False


def _plugin_repair_reasons(health: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for plugin_id in _PLUGIN_IDS:
        entry = health.get(plugin_id)
        if not isinstance(entry, dict):
            continue
        if plugin_needs_repair(plugin_id, entry):
            msg = str(entry.get("message") or entry.get("status") or "error").strip()
            reasons.append(f"{plugin_id}: {msg[:120]}")
    return reasons


def _no_response_reasons(diagnostics: dict[str, Any]) -> list[str]:
    repair = diagnostics.get("modbus_repair") if isinstance(diagnostics.get("modbus_repair"), dict) else {}
    no_response = repair.get("no_response_modules") if isinstance(repair.get("no_response_modules"), list) else []
    reasons: list[str] = []
    for module in no_response:
        token = f"modbus_no_response:{module}"
        if token not in reasons:
            reasons.append(token)
    return reasons


def analyze_repair_needs(identify: dict[str, Any] | None) -> tuple[bool, list[str]]:
    """Return whether host stack restart is recommended and human-readable reasons."""
    if not isinstance(identify, dict):
        return False, []
    health = _health_map(identify)
    diagnostics = identify.get("diagnostics") if isinstance(identify.get("diagnostics"), dict) else {}

    reasons = _plugin_repair_reasons(health)
    reasons.extend(_no_response_reasons(diagnostics))

    ws = diagnostics.get("modbus_waveshare_diagnose")
    if isinstance(ws, dict) and ws.get("serial_handles_stale"):
        reasons.append("serial_handles_stale")

    platform = identify.get("platform") if isinstance(identify.get("platform"), dict) else {}
    topology = str(platform.get("modbus_topology") or platform.get("modbus_topology_mode") or "")
    if topology == "separate-adapters" and reasons:
        reasons.append("topology:separate-adapters (jeden USB-RS485 na modul)")

    return bool(reasons), reasons


def modbus_exclusive_scan_recommended(identify: dict[str, Any] | None) -> bool:
    if not isinstance(identify, dict):
        return False
    diagnostics = identify.get("diagnostics") if isinstance(identify.get("diagnostics"), dict) else {}
    ws = diagnostics.get("modbus_waveshare_diagnose")
    if isinstance(ws, dict) and ws.get("serial_handles_stale"):
        return True
    return modbus_plugins_need_repair(identify)


def overall_stack_healthy(identify: dict[str, Any] | None, *, require_motors: bool = True) -> bool:
    if not isinstance(identify, dict):
        return False
    health = _health_map(identify)
    plugins = list(_PLUGIN_IDS) if require_motors else ("modbus-io", "modbus-adc")
    for plugin_id in plugins:
        entry = health.get(plugin_id)
        if not isinstance(entry, dict):
            if plugin_id.startswith("modbus"):
                return False
            continue
        if plugin_needs_repair(plugin_id, entry):
            return False
        status = str(entry.get("status") or "").lower()
        if plugin_id.startswith("modbus") and status not in {"connected", "ok"}:
            if entry.get("compatible") is not True:
                return False
    return True


def build_summary(
    *,
    repairs: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    before_ok: bool,
    after_ok: bool,
    reasons: list[str],
) -> str:
    parts: list[str] = []
    if repairs:
        ok_repairs = sum(1 for entry in repairs if entry.get("ok"))
        parts.append(f"naprawa stosu: {ok_repairs}/{len(repairs)}")
    if actions:
        ok_actions = sum(1 for entry in actions if entry.get("ok"))
        parts.append(f"akcje Modbus: {ok_actions}/{len(actions)}")
    parts.append(f"stan: {'OK' if after_ok else 'wymaga uwagi'}")
    if not after_ok and reasons:
        parts.append(f"({'; '.join(reasons[:3])})")
    if before_ok and after_ok:
        return "Auto-diagnoza: sprzet OK, restart nie był potrzebny."
    return "Auto-diagnoza zakończona — " + ", ".join(parts) + "."
