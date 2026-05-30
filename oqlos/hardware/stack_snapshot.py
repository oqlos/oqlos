"""Single entry for hardware autodetection and configuration-cycle metadata."""

from __future__ import annotations

from typing import Any


def _lazy_hardware_api():
    from oqlos.api import hardware as hw

    return hw


def build_hardware_stack_snapshot(health: dict[str, Any] | None) -> dict[str, Any]:
    """
    Collect platform, plugin health, Modbus preflight, stale-serial state, and wizard plan.

    Used by /api/v1/hardware/stack/snapshot and should stay the only place that assembles
    this bundle for OqlOS consumers (c2004 connect-scenario proxies it).
    """
    hw = _lazy_hardware_api()
    health_payload = health if isinstance(health, dict) else {}
    platform = hw._detect_runtime_platform()
    ports = hw._modbus_runtime_serial_ports()
    stale = hw._modbus_health_serial_stale(health_payload)
    gateway = hw._gw()
    preflight: dict[str, Any] = {}
    try:
        if gateway is not None and hasattr(gateway, "modbus_preflight_report"):
            report = gateway.modbus_preflight_report()
            if isinstance(report, dict):
                preflight = report
    except Exception as exc:
        preflight = {
            "ok": False,
            "topology": "unknown",
            "modules": [],
            "issues": [{"severity": "error", "code": "preflight_exception", "message": str(exc)}],
            "recommended": {},
        }

    wizard_plan = hw._modbus_wizard_plan()
    actions: list[dict[str, str]] = []
    if stale:
        actions.append(
            {
                "code": "restart_oqlos",
                "message": "Restart OqlOS to reopen USB serial handles after tty remap.",
                "command_hint": "systemctl --user restart oqlos-hardware-api.service",
            }
        )
    if not stale:
        for plugin_id in ("modbus-io", "modbus-adc"):
            entry = health_payload.get(plugin_id)
            if not isinstance(entry, dict) or entry.get("compatible"):
                continue
            message = str(entry.get("message") or "").lower()
            if "timed out" in message or "no response" in message:
                actions.append(
                    {
                        "code": "check_modbus_physical",
                        "message": f"{plugin_id}: verify power, RS485 A/B/GND, slave ID and baud 9600.",
                        "command_hint": "make hardware-modbus-probe",
                    }
                )

    return {
        "ok": True,
        "source": "oqlos.hardware.stack_snapshot",
        "platform": platform,
        "health": health_payload,
        "modbus_preflight": preflight,
        "modbus_ports": ports,
        "serial_handles_stale": stale,
        "modbus_topology": ports.get("topology") or platform.get("modbus_topology"),
        "wizard_plan": wizard_plan,
        "recommended_actions": actions,
        "configuration_cycle": {
            "detect": "stack_snapshot",
            "configure": "modbus/wizard/plan",
            "verify": "/api/v1/hardware/modbus/waveshare-diagnose",
        },
    }
