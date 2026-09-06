"""Safe live Modbus IO verify (read + optional safe-off write).

Health can report ``modbus-io`` connected while callers still fail when they
send ``args`` instead of ``params``, or when the slave briefly drops. This
report always exercises the live plugin path with explicit ``params``.
"""

from __future__ import annotations

from typing import Any

from oqlos.api.hardware_gateway import try_get_hardware_gateway
from oqlos.errors.c2004_catalog_generated import c2004_code_for_issue
from oqlos.hardware.plugins._shared import hardware_failure_payload


def _step(name: str, ok: bool, **extra: Any) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), **extra}


async def build_modbus_io_verify_report(*, write_safe_off: bool = True) -> dict[str, Any]:
    """Probe modbus-io through the live gateway/plugin (bounded, no baud scan)."""
    gateway = try_get_hardware_gateway()
    steps: list[dict[str, Any]] = []
    repairs: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    if gateway is None:
        issue_code = "hw_modbus_no_response"
        return hardware_failure_payload(
            c2004_code_for_issue(issue_code), component="modbus-io",
            issue_code=issue_code,
            steps=[_step("gateway", False, error="hardware gateway unavailable")],
            issues=[
                {
                    "code": issue_code,
                    "message": "Hardware gateway is not initialized",
                }
            ],
            repairs=[
                {
                    "id": "restart-oqlos",
                    "auto_executable": True,
                    "hint": "Restart oqlos-hardware-api so the gateway binds modbus-io",
                }
            ],
            snapshot=None,
        )

    await gateway.ensure_initialized()
    plugin = await gateway._get_or_connect_plugin("modbus-io")
    if plugin is None:
        issue_code = "hw_modbus_no_response"
        issues.append(
            {
                "code": issue_code,
                "message": "modbus-io plugin instance unavailable",
            }
        )
        repairs.append(
            {
                "id": "modbus-reconnect",
                "auto_executable": True,
                "endpoint": "POST /api/v3/hardware/diagnosis/repair?devices=modbus",
                "hint": "Reconnect modbus-io via safe diagnosis repair",
            }
        )
        return hardware_failure_payload(
            c2004_code_for_issue(issue_code), component="modbus-io",
            issue_code=issue_code,
            steps=[_step("connect", False)],
            issues=issues,
            repairs=repairs,
            snapshot=None,
        )

    health = await plugin.health_check()
    status_value = getattr(health.status, "value", health.status)
    health_ok = bool(getattr(health, "compatible", False)) and str(status_value).lower() in {
        "connected",
        "ok",
    }
    steps.append(
        _step(
            "health",
            health_ok,
            status=str(status_value),
            message=str(getattr(health, "message", "")),
        )
    )

    snapshot = await plugin.execute_command("read_io_snapshot", {})
    snapshot_ok = bool(isinstance(snapshot, dict) and snapshot.get("success"))
    snapshot_data = snapshot.get("data") if isinstance(snapshot, dict) else None
    steps.append(
        _step(
            "read_io_snapshot",
            snapshot_ok,
            error=None if snapshot_ok else str((snapshot or {}).get("error") or snapshot)[:200],
            device_id_register=(snapshot_data or {}).get("device_id_register")
            if isinstance(snapshot_data, dict)
            else None,
            uart_register=(snapshot_data or {}).get("uart_register")
            if isinstance(snapshot_data, dict)
            else None,
        )
    )
    if not snapshot_ok:
        issue_code = "hw_modbus_no_response"
        issues.append(
            {
                "code": issue_code,
                "message": "read_io_snapshot failed — slave silent or wrong baud/ID",
            }
        )
        repairs.append(
            {
                "id": "modbus-physical-check",
                "auto_executable": False,
                "hint": "Verify Waveshare power, RS485 A/B, GND, slave ID 2, baud 4800 8N1",
            }
        )
        repairs.append(
            {
                "id": "modbus-reconnect",
                "auto_executable": True,
                "endpoint": "POST /api/v3/hardware/diagnosis/repair?devices=modbus",
                "hint": "Reconnect modbus-io after physical check",
            }
        )
        return hardware_failure_payload(
            c2004_code_for_issue(issue_code), component="modbus-io",
            issue_code=issue_code,
            steps=steps,
            issues=issues,
            repairs=repairs,
            snapshot=snapshot_data if isinstance(snapshot_data, dict) else None,
        )

    write_ok = True
    if write_safe_off:
        write = await plugin.execute_command(
            "set_valve", {"valve_id": "valve-4", "value": False}
        )
        write_ok = bool(isinstance(write, dict) and write.get("success"))
        steps.append(
            _step(
                "set_valve_valve-4_off",
                write_ok,
                error=None if write_ok else str((write or {}).get("error") or write)[:200],
            )
        )
        if not write_ok:
            issue_code = "hw_modbus_no_response"
            issues.append(
                {
                    "code": issue_code,
                    "message": "set_valve(valve-4,false) failed after successful snapshot",
                }
            )
            repairs.append(
                {
                    "id": "modbus-reconnect",
                    "auto_executable": True,
                    "endpoint": "POST /api/v3/hardware/diagnosis/repair?devices=modbus",
                    "hint": "Reconnect modbus-io; retry io-verify before physical swap",
                }
            )

    ok = health_ok and snapshot_ok and write_ok
    issue_code = None if ok else "hw_modbus_no_response"
    if ok:
        repairs.append(
            {
                "id": "none",
                "auto_executable": False,
                "hint": "Modbus IO RTU path verified (read + safe valve-4 off)",
            }
        )
    return {
        "ok": ok,
        "issue_code": issue_code,
        "code": c2004_code_for_issue(issue_code) if issue_code else None,
        "steps": steps,
        "issues": issues,
        "repairs": repairs,
        "snapshot": snapshot_data if isinstance(snapshot_data, dict) else None,
        "contract": {
            "plugin_id": "modbus-io",
            "expected_device_id": 2,
            "expected_baud": 4800,
            "expected_parity": "N",
            "probe_valve_id": "valve-4",
        },
    }
