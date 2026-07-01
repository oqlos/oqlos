"""Per-device hardware diagnosis and safe in-process recovery (OqlOS runtime)."""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from typing import Any

from oqlos.hardware.diagnosis_device_actions import (
    build_report_global_actions,
    diagnose_barcode_scanner,
    diagnose_plugin_devices,
)
from oqlos.hardware.diagnosis_plugin_health import (
    health_map,
    is_stale_hardware_entry,  # noqa: F401 — re-exported for oqlos.hardware.client.autorepair
    is_stale_hardware_message,  # noqa: F401 — re-exported for oqlos.hardware.client.autorepair
    modbus_plugins_need_repair,
    plugin_is_healthy,
    plugin_needs_repair,
)
from oqlos.hardware.diagnosis_types import (
    DeviceDiagnosis,  # noqa: F401 — re-exported for tests / API consumers
    DiagnosisAction,
    DiagnosisReport,
    action_dict,
    report_to_dict,  # noqa: F401 — re-exported for oqlos.api.hardware_diagnosis_routes
)
from oqlos.hardware.plugins.registry import PluginRegistry
from oqlos.hardware.stack_snapshot import build_hardware_stack_snapshot

_MONITOR_PLUGINS = ("modbus-io", "modbus-adc", "motor-tic249", "motor-dri0050")
_OQLOS_SAFE_PLUGINS = ("modbus-io", "modbus-adc", "motor-tic249", "motor-dri0050")

# Backward-compatible aliases
_health_map = health_map
_action_dict = action_dict


def _report_device_status(report: DiagnosisReport, plugin_id: str) -> str:
    dev = report.devices.get(plugin_id)
    return str(dev.status if dev else "")


def _adapter_index(identify: dict[str, Any]) -> dict[str, dict[str, Any]]:
    adapters = identify.get("adapters")
    if not isinstance(adapters, list):
        return {}
    return {str(entry["id"]): entry for entry in adapters if isinstance(entry, dict) and entry.get("id")}


def _build_stack_snapshot(health: dict[str, Any]) -> dict[str, Any]:
    """Call build_hardware_stack_snapshot safely, returning empty dict on error."""
    try:
        return build_hardware_stack_snapshot(health)
    except Exception:
        return {}


def _resolve_host_recover() -> str:
    """Return the best available host recovery mechanism identifier."""
    return (
        os.environ.get("OQLOS_HOST_RECOVER_HOOK", "").strip()
        or os.environ.get("OQLOS_RUNTIME_CONTROL_SCRIPT", "").strip()
        or ("systemd" if shutil.which("systemctl") else "")
    )


def build_diagnosis_report(identify: dict[str, Any]) -> DiagnosisReport:
    """Build per-device diagnosis from an identify payload (same shape as GET /identify)."""
    platform = identify.get("platform") if isinstance(identify.get("platform"), dict) else {}
    health = health_map(identify)
    adapters = _adapter_index(identify)
    topology = str(platform.get("modbus_topology") or platform.get("modbus_topology_mode") or "").strip()
    serial_ports = [str(p) for p in (platform.get("serial_ports") or []) if p]
    host_recover = _resolve_host_recover()
    c2004_root = os.environ.get("C2004_ROOT", "/home/tom/github/maskservice/c2004")

    devices = diagnose_plugin_devices(health, adapters, platform, topology, host_recover)
    devices["barcode-scanner"] = diagnose_barcode_scanner(adapters)

    modbus_bad = modbus_plugins_need_repair(identify)
    motors_bad = any(devices[d].status == "error" for d in ("motor-tic249", "motor-dri0050"))
    global_actions = build_report_global_actions(modbus_bad, motors_bad, c2004_root, host_recover)

    error_devices = [d.device_id for d in devices.values() if d.status == "error"]
    requires_full = modbus_bad or modbus_plugins_need_repair(identify)
    snapshot = _build_stack_snapshot(health)

    return DiagnosisReport(
        environment={
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "topology": topology,
            "runtime_control_available": bool(host_recover),
            "host_recover_hook": host_recover or None,
            "serial_ports": serial_ports,
            "stack_snapshot_ok": snapshot.get("ok"),
            "serial_handles_stale": snapshot.get("serial_handles_stale"),
        },
        devices=devices,
        global_actions=global_actions,
        ok=not error_devices,
        message=(
            "Diagnostyka: wszystkie monitorowane urządzenia OK."
            if not error_devices
            else "Diagnostyka: wymaga uwagi — " + ", ".join(error_devices)
        ),
        requires_full_stack_restart=requires_full,
    )


def _should_include_host_action(
    action: DiagnosisAction,
    seen: set[str],
    saw_make: bool,
    motor_only: bool,
    failed: set[str],
) -> tuple[bool, bool]:
    """Check whether to include a host-scope action. Returns (include, saw_make_now)."""
    if action.scope != "host" or action.id in seen:
        return False, saw_make
    if action.kind == "make_target":
        if saw_make:
            return False, saw_make
        modbus_still = any(pid.startswith("modbus") for pid in failed)
        if motor_only and not modbus_still:
            return False, saw_make
        return True, True
    if action.id.endswith("-hardware-up"):
        return False, saw_make
    if action.id.startswith("dri0050-restart"):
        return False, saw_make
    return True, saw_make


def _host_actions_from_report(
    report: DiagnosisReport,
    *,
    still_failed: list[str] | None = None,
) -> list[dict[str, Any]]:
    actions: list[DiagnosisAction] = list(report.global_actions)
    for dev in report.devices.values():
        actions.extend(dev.recommended_actions)
    host: list[dict[str, Any]] = []
    seen: set[str] = set()
    saw_make = False
    failed = set(still_failed or [])
    motor_only = bool(failed) and all(pid.startswith("motor") for pid in failed)
    for action in sorted(actions, key=lambda a: (a.priority, a.id)):
        include, saw_make = _should_include_host_action(action, seen, saw_make, motor_only, failed)
        if include:
            seen.add(action.id)
            host.append(action_dict(action))
    return host


def _recover_targets(report: DiagnosisReport, health: dict[str, Any]) -> list[str]:
    """Only plugins marked error in diagnosis AND unhealthy in live health."""
    targets: list[str] = []
    for pid in _OQLOS_SAFE_PLUGINS:
        if _report_device_status(report, pid) != "error":
            continue
        entry = health.get(pid) if isinstance(health.get(pid), dict) else {}
        if plugin_is_healthy(entry):
            continue
        if plugin_needs_repair(pid, entry):
            targets.append(pid)
    return targets


_SIDECAR_DOWN_MARKERS = ("connection attempts failed", "http 503", "503", "connect returned false")


def _should_force_sidecar_restart(entry: dict[str, Any], *, extra_markers: tuple[str, ...] = ()) -> bool:
    if not entry:
        return True
    msg = str(entry.get("message") or "").lower()
    return any(marker in msg for marker in (*_SIDECAR_DOWN_MARKERS, *extra_markers))


async def _repair_dri0050_if_needed(
    targets: list[str],
    health_before: dict[str, Any],
    repairs: list[dict[str, Any]],
) -> None:
    """Ensure dri0050 sidecar is running if it's in the repair target list."""
    if "motor-dri0050" not in targets:
        return
    from oqlos.hardware.sidecar_control import ensure_dri0050_sidecar

    entry = health_before.get("motor-dri0050") if isinstance(health_before.get("motor-dri0050"), dict) else {}
    force = _should_force_sidecar_restart(entry)
    repairs.append(await ensure_dri0050_sidecar(force_restart=force))


async def _repair_tic249_if_needed(
    targets: list[str],
    health_before: dict[str, Any],
    repairs: list[dict[str, Any]],
) -> None:
    """Restart hw-tic249.service if the lung motor plugin is in the repair target list."""
    if "motor-tic249" not in targets:
        return
    from oqlos.hardware.sidecar_control import ensure_tic249_sidecar

    entry = health_before.get("motor-tic249") if isinstance(health_before.get("motor-tic249"), dict) else {}
    force = _should_force_sidecar_restart(entry, extra_markers=("errno 19",))
    repairs.append(await ensure_tic249_sidecar(force_restart=force))


async def execute_safe_recover(gateway: Any, report: DiagnosisReport) -> dict[str, Any]:
    """Reconnect failed plugins inside OqlOS; return host_actions for sidecars."""
    repairs: list[dict[str, Any]] = []
    health_before = await gateway.health()
    targets = _recover_targets(report, health_before)
    await _repair_dri0050_if_needed(targets, health_before, repairs)
    await _repair_tic249_if_needed(targets, health_before, repairs)
    if not targets and report.requires_full_stack_restart:
        return {
            "ok": False,
            "strategy": "needs-host-hardware-up",
            "repairs": repairs,
            "host_actions": _host_actions_from_report(report),
        }
    for plugin_id in targets:
        step = f"reconnect-{plugin_id}"
        ok = False
        try:
            if plugin_id.startswith("modbus"):
                await PluginRegistry.disconnect_plugin(plugin_id)
                config = gateway._plugin_configs.get(plugin_id)
                if config:
                    ok = await PluginRegistry.connect_plugin(plugin_id, config)
            else:
                instance = await gateway._get_or_connect_plugin(plugin_id)
                ok = instance is not None
        except Exception as exc:
            repairs.append({"step": step, "ok": False, "error": str(exc)})
            continue
        repairs.append({"step": step, "ok": bool(ok)})
    health_after = await gateway.health()
    still_bad = [
        pid
        for pid in _MONITOR_PLUGINS
        if plugin_needs_repair(pid, health_after.get(pid) if isinstance(health_after.get(pid), dict) else {})
    ]
    return {
        "ok": not still_bad,
        "strategy": "oqlos-safe",
        "repairs": repairs,
        "host_actions": _host_actions_from_report(report, still_failed=still_bad),
        "still_failed": still_bad,
    }
