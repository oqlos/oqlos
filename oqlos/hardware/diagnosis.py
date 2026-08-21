"""Per-device hardware diagnosis and safe in-process recovery (OqlOS runtime)."""

from __future__ import annotations

import os
import shutil
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from oqlos.hardware.diagnosis_device_actions import (
    build_report_global_actions,
    diagnose_analog_input_devices,
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

_OQLOS_SAFE_PLUGINS = (
    "modbus-io",
    "io-m5-4in8out",
    "modbus-adc",
    "motor-tic249",
    "motor-dri0050",
)
_MOTOR_PLUGIN_IDS = frozenset({"motor-tic249", "motor-dri0050"})
_MODBUS_PLUGIN_IDS = frozenset({"modbus-io", "modbus-adc"})

# Backward-compatible aliases
_health_map = health_map
_action_dict = action_dict


def resolve_recover_plugin_ids(devices: str) -> tuple[str, ...]:
    selector = str(devices or "").strip().lower()
    if selector == "motors":
        return tuple(sorted(_MOTOR_PLUGIN_IDS))
    if selector == "modbus":
        return tuple(sorted(_MODBUS_PLUGIN_IDS))
    if selector in _OQLOS_SAFE_PLUGINS:
        return (selector,)
    return _OQLOS_SAFE_PLUGINS


def _is_motor_global_action(action: object) -> bool:
    if not isinstance(action, dict):
        return False
    action_id = str(action.get("id") or "")
    device_id = str(action.get("device_id") or "")
    return (
        not action_id.startswith("global-modbus")
        and not device_id.startswith("modbus")
        and (device_id in _MOTOR_PLUGIN_IDS or device_id == "*")
    )


def filter_diagnosis_dict_for_devices(payload: dict[str, Any], devices: str) -> dict[str, Any]:
    selector = str(devices or "").strip().lower()
    if selector not in {"motors", "modbus", *_OQLOS_SAFE_PLUGINS}:
        return payload
    selected = set(resolve_recover_plugin_ids(selector))
    device_map = payload.get("devices") if isinstance(payload.get("devices"), dict) else {}
    filtered_devices = {
        key: value for key, value in device_map.items() if key in selected
    }
    if selected <= _MOTOR_PLUGIN_IDS:
        global_actions = [
            action
            for action in (payload.get("global_actions") or [])
            if _is_motor_global_action(action)
        ]
    else:
        global_actions = [
            action
            for action in (payload.get("global_actions") or [])
            if isinstance(action, dict)
            and (
                str(action.get("device_id") or "") in selected
                or str(action.get("id") or "").startswith("global-modbus")
            )
        ]
    return {
        **payload,
        "devices": filtered_devices,
        "global_actions": global_actions,
    }


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


def _diagnosis_platform(identify: dict[str, Any]) -> dict[str, Any]:
    platform = identify.get("platform")
    return platform if isinstance(platform, dict) else {}


def _diagnosis_topology(platform: dict[str, Any]) -> str:
    return str(platform.get("modbus_topology") or platform.get("modbus_topology_mode") or "").strip()


def _diagnosis_devices(
    identify: dict[str, Any], health: dict[str, Any], adapters: dict[str, Any],
    platform: dict[str, Any], topology: str, host_recover: str,
) -> dict[str, DeviceDiagnosis]:
    devices = diagnose_plugin_devices(
        health, adapters, platform, topology, host_recover,
        hardware_mode=str(identify.get("mode") or "").strip().lower(),
    )
    devices.update(diagnose_analog_input_devices(identify, platform))
    devices["barcode-scanner"] = diagnose_barcode_scanner(adapters)
    return devices


def _diagnosis_environment(
    identify: dict[str, Any], platform: dict[str, Any], topology: str,
    host_recover: str, snapshot: dict[str, Any],
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "topology": topology,
        "hardware_mode": str(identify.get("mode") or "").strip().lower() or None,
        "runtime_control_available": bool(host_recover),
        "host_recover_hook": host_recover or None,
        "serial_ports": [str(port) for port in (platform.get("serial_ports") or []) if port],
        "analog_input_devices": list(platform.get("analog_input_devices") or []),
        "stack_snapshot_ok": snapshot.get("ok"),
        "serial_handles_stale": snapshot.get("serial_handles_stale"),
    }


def _diagnosis_message(error_devices: list[str]) -> str:
    if not error_devices:
        return "Diagnostyka: wszystkie monitorowane urządzenia OK."
    return "Diagnostyka: wymaga uwagi — " + ", ".join(error_devices)


def build_diagnosis_report(identify: dict[str, Any]) -> DiagnosisReport:
    """Build per-device diagnosis from an identify payload (same shape as GET /identify)."""
    platform = _diagnosis_platform(identify)
    health = health_map(identify)
    adapters = _adapter_index(identify)
    topology = _diagnosis_topology(platform)
    host_recover = _resolve_host_recover()
    c2004_root = os.environ.get("C2004_ROOT", "/home/tom/github/maskservice/c2004")
    devices = _diagnosis_devices(identify, health, adapters, platform, topology, host_recover)

    valve_ids = ("io-m5-4in8out", "modbus-io")
    healthy_valves = [
        plugin_id
        for plugin_id in valve_ids
        if plugin_is_healthy(
            health.get(plugin_id) if isinstance(health.get(plugin_id), dict) else None
        )
    ]
    if healthy_valves:
        for plugin_id in valve_ids:
            device = devices.get(plugin_id)
            if device is not None and device.status == "error":
                device.status = "degraded"
                device.issues.append(
                    "Kontroler zapasowy jest niedostępny; zawory obsługuje "
                    + healthy_valves[0]
                    + "."
                )

    modbus_bad = modbus_plugins_need_repair(identify)
    motors_bad = any(devices[d].status == "error" for d in ("motor-tic249", "motor-dri0050"))
    global_actions = build_report_global_actions(modbus_bad, motors_bad, c2004_root, host_recover)
    error_devices = [d.device_id for d in devices.values() if d.status == "error"]
    requires_full = modbus_bad or modbus_plugins_need_repair(identify)
    snapshot = _build_stack_snapshot(health)

    return DiagnosisReport(
        environment=_diagnosis_environment(identify, platform, topology, host_recover, snapshot),
        devices=devices,
        global_actions=global_actions,
        ok=not error_devices,
        message=_diagnosis_message(error_devices),
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


def _has_safe_auto_action(report: DiagnosisReport, plugin_id: str) -> bool:
    """The report itself offers a zero-risk in-process repair for this device."""
    device = report.devices.get(plugin_id)
    if device is None:
        return False
    return any(
        action.auto_executable
        and action.scope == "oqlos"
        and action.actuation_risk in (None, "none")
        for action in device.recommended_actions
    )


def _recover_targets(
    report: DiagnosisReport,
    health: dict[str, Any],
    *,
    plugin_ids: tuple[str, ...] | None = None,
) -> list[str]:
    """Plugins that diagnosis wants repaired AND that are unhealthy in live health.

    A device that lost its only role is reported `degraded`, not `error` — a
    valve module demoted to fallback by the M5 migration is the live example. It
    still advertises `auto_executable` reconnect actions, so filtering on `error`
    alone left the operator with a repair button that reconnected nothing.
    """
    allowed = plugin_ids or _OQLOS_SAFE_PLUGINS
    targets: list[str] = []
    for pid in allowed:
        status = _report_device_status(report, pid)
        if status != "error" and not (
            status == "degraded" and _has_safe_auto_action(report, pid)
        ):
            continue
        entry = health.get(pid) if isinstance(health.get(pid), dict) else {}
        if plugin_is_healthy(entry):
            continue
        if plugin_needs_repair(pid, entry):
            targets.append(pid)
    return targets


def _still_failed_plugins(
    report: DiagnosisReport,
    health: dict[str, Any],
    allowed: tuple[str, ...],
) -> list[str]:
    """Return failed configured devices, excluding intentionally disabled ones."""
    return [
        plugin_id
        for plugin_id in allowed
        if _report_device_status(report, plugin_id) == "error"
        and plugin_needs_repair(
            plugin_id,
            health.get(plugin_id) if isinstance(health.get(plugin_id), dict) else {},
        )
    ]


_SIDECAR_DOWN_MARKERS = ("connection attempts failed", "http 503", "503", "connect returned false")


def _should_force_sidecar_restart(entry: dict[str, Any], *, extra_markers: tuple[str, ...] = ()) -> bool:
    if not entry:
        return True
    msg = str(entry.get("message") or "").lower()
    return any(marker in msg for marker in (*_SIDECAR_DOWN_MARKERS, *extra_markers))


async def _repair_sidecar_if_needed(
    plugin_id: str,
    ensure_sidecar: Callable[..., Awaitable[dict[str, Any]]],
    targets: list[str],
    health_before: dict[str, Any],
    repairs: list[dict[str, Any]],
    *,
    extra_markers: tuple[str, ...] = (),
) -> None:
    """Ensure the plugin's sidecar is running if it's in the repair target list."""
    if plugin_id not in targets:
        return
    entry = health_before.get(plugin_id) if isinstance(health_before.get(plugin_id), dict) else {}
    force = _should_force_sidecar_restart(entry, extra_markers=extra_markers)
    repairs.append(await ensure_sidecar(force_restart=force))


async def execute_safe_recover(
    gateway: Any,
    report: DiagnosisReport,
    *,
    plugin_ids: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Reconnect failed plugins inside OqlOS; return host_actions for sidecars."""
    from oqlos.hardware.sidecar_control import ensure_dri0050_sidecar, ensure_tic249_sidecar

    allowed = plugin_ids or _OQLOS_SAFE_PLUGINS
    repairs: list[dict[str, Any]] = []
    health_before = await gateway.health()
    targets = _recover_targets(report, health_before, plugin_ids=allowed)
    await _repair_sidecar_if_needed("motor-dri0050", ensure_dri0050_sidecar, targets, health_before, repairs)
    await _repair_sidecar_if_needed(
        "motor-tic249", ensure_tic249_sidecar, targets, health_before, repairs, extra_markers=("errno 19",)
    )
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
                reconnect = getattr(gateway, "apply_modbus_user_settings", None)
                if callable(reconnect):
                    result = await reconnect({plugin_id})
                    requested_result = next(
                        (
                            item
                            for item in result.get("reconnects", [])
                            if item.get("plugin_id") == plugin_id
                        ),
                        None,
                    )
                    # Recovery is successful only when the requested logical
                    # plugin was actually reconnected.  ``all([])``-style
                    # aggregate success must not turn a missing config/result
                    # into a false-positive repair.
                    ok = bool(
                        requested_result is not None
                        and requested_result.get("ok")
                    )
                else:
                    # Compatibility for small/local gateways. Keep both runtime
                    # maps synchronized even on the legacy recovery path.
                    gateway._plugins.pop(plugin_id, None)
                    await PluginRegistry.disconnect_plugin(plugin_id)
                    config = gateway._plugin_configs.get(plugin_id)
                    if config:
                        ok = await PluginRegistry.connect_plugin(plugin_id, config)
                        instance = PluginRegistry.get_instance(plugin_id)
                        if ok and instance is not None:
                            gateway._plugins[plugin_id] = instance
            else:
                instance = await gateway._get_or_connect_plugin(plugin_id)
                ok = instance is not None
        except Exception as exc:
            repairs.append({"step": step, "ok": False, "error": str(exc)})
            continue
        repairs.append({"step": step, "ok": bool(ok)})
    health_after = await gateway.health()
    still_bad = _still_failed_plugins(report, health_after, allowed)
    return {
        "ok": not still_bad,
        "strategy": "oqlos-safe",
        "repairs": repairs,
        "host_actions": _host_actions_from_report(report, still_failed=still_bad),
        "still_failed": still_bad,
    }
