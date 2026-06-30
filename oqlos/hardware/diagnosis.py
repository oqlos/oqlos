"""Per-device hardware diagnosis and safe in-process recovery (OqlOS runtime)."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from oqlos.hardware.plugins.registry import PluginRegistry
from oqlos.hardware.stack_snapshot import build_hardware_stack_snapshot

DeviceStatus = Literal["ok", "degraded", "error", "unknown", "skipped", "not_present"]
ActionKind = Literal["make_target", "systemd", "docker", "probe", "wizard", "manual", "http", "oqlos"]

_STALE_MARKERS = (
    "errno 19",
    "no such device",
    "errno 5",
    "input/output error",
    "serial_handle_stale",
    "serial-stale",
    "http 503",
    "http 500",
    "timed out",
    "write timeout",
)

_MONITOR_PLUGINS = ("modbus-io", "modbus-adc", "motor-tic249", "motor-dri0050")
_OQLOS_SAFE_PLUGINS = ("modbus-io", "modbus-adc", "motor-tic249", "motor-dri0050")


@dataclass(frozen=True)
class DiagnosisAction:
    id: str
    device_id: str
    label: str
    kind: ActionKind
    priority: int
    command: str | None = None
    make_target: str | None = None
    auto_executable: bool = False
    detail: str = ""
    scope: str = "oqlos"  # oqlos | host


@dataclass
class DeviceDiagnosis:
    device_id: str
    display_name: str
    status: DeviceStatus
    health_summary: str
    issues: list[str] = field(default_factory=list)
    environment: dict[str, Any] = field(default_factory=dict)
    recommended_actions: list[DiagnosisAction] = field(default_factory=list)


@dataclass
class DiagnosisReport:
    environment: dict[str, Any]
    devices: dict[str, DeviceDiagnosis]
    global_actions: list[DiagnosisAction]
    ok: bool
    message: str
    requires_full_stack_restart: bool = False


def _health_map(identify: dict[str, Any]) -> dict[str, Any]:
    diagnostics = identify.get("diagnostics") if isinstance(identify, dict) else {}
    health = diagnostics.get("health") if isinstance(diagnostics, dict) else {}
    return health if isinstance(health, dict) else {}


def is_stale_hardware_message(message: Any) -> bool:
    return any(marker in str(message or "").lower() for marker in _STALE_MARKERS)


def is_stale_hardware_entry(entry: dict[str, Any] | None) -> bool:
    if not isinstance(entry, dict):
        return False
    return is_stale_hardware_message(entry.get("message") or entry.get("status") or "")


def plugin_is_healthy(entry: dict[str, Any] | None) -> bool:
    """Stable OK — do not disconnect/reconnect when true."""
    if not isinstance(entry, dict):
        return False
    status = str(entry.get("status") or "").lower()
    return entry.get("compatible") is True and status in {"connected", "ok", "healthy"}


def plugin_needs_repair(plugin_id: str, entry: dict[str, Any] | None) -> bool:
    if plugin_is_healthy(entry):
        return False
    if not isinstance(entry, dict):
        return False
    message = str(entry.get("message") or "").lower()
    status = str(entry.get("status") or "").lower()
    if any(marker in message for marker in _STALE_MARKERS):
        return True
    if entry.get("compatible") is not True:
        return True
    if status in {"error", "offline", "disabled", "no-access", "device-stale"}:
        return True
    return False


def _report_device_status(report: DiagnosisReport, plugin_id: str) -> str:
    dev = report.devices.get(plugin_id)
    return str(dev.status if dev else "")


def modbus_plugins_need_repair(identify: dict[str, Any] | None) -> bool:
    health = _health_map(identify or {})
    for key in ("modbus-io", "modbus-adc"):
        if plugin_needs_repair(key, health.get(key) if isinstance(health.get(key), dict) else {}):
            return True
    return False


def _adapter_index(identify: dict[str, Any]) -> dict[str, dict[str, Any]]:
    adapters = identify.get("adapters")
    if not isinstance(adapters, list):
        return {}
    return {str(entry["id"]): entry for entry in adapters if isinstance(entry, dict) and entry.get("id")}


def _message_lower(entry: dict | None) -> str:
    if not entry:
        return ""
    return str(entry.get("message") or entry.get("status") or "").lower()


def _infer_status(plugin_id: str, entry: dict | None, *, present: bool = True) -> DeviceStatus:
    if not present:
        return "not_present"
    if not entry:
        return "unknown"
    if plugin_needs_repair(plugin_id, entry):
        return "error"
    status = str(entry.get("status") or "").lower()
    if status in {"connected", "ok"} and entry.get("compatible") is not False:
        return "ok"
    return "degraded"


def _action_dict(action: DiagnosisAction) -> dict[str, Any]:
    return {
        "id": action.id,
        "device_id": action.device_id,
        "label": action.label,
        "kind": action.kind,
        "priority": action.priority,
        "command": action.command,
        "make_target": action.make_target,
        "auto_executable": action.auto_executable,
        "detail": action.detail,
        "scope": action.scope,
    }


def report_to_dict(report: DiagnosisReport) -> dict[str, Any]:
    return {
        "ok": report.ok,
        "message": report.message,
        "requires_full_stack_restart": report.requires_full_stack_restart,
        "environment": dict(report.environment),
        "devices": {
            key: {
                "device_id": dev.device_id,
                "display_name": dev.display_name,
                "status": dev.status,
                "health_summary": dev.health_summary,
                "issues": list(dev.issues),
                "environment": dict(dev.environment),
                "recommended_actions": [_action_dict(a) for a in dev.recommended_actions],
            }
            for key, dev in report.devices.items()
        },
        "global_actions": [_action_dict(a) for a in report.global_actions],
        "source": "oqlos.hardware.diagnosis",
    }


def _add_modbus_device_actions(
    dev: "DeviceDiagnosis",
    plugin_id: str,
    status: str,
    msg: str,
    platform: "dict[str, Any]",
) -> None:
    port = (
        platform.get("modbus_io_serial_port")
        if plugin_id == "modbus-io"
        else platform.get("modbus_adc_serial_port")
    )
    dev.environment["serial_port"] = port
    if status == "ok":
        return
    if "errno 19" in msg or "no such device" in msg:
        dev.issues.append("Nieaktualny port USB/RS485 po re-enumeracji.")
    dev.recommended_actions.append(
        DiagnosisAction(
            id=f"{plugin_id}-reconnect",
            device_id=plugin_id,
            label=f"Reconnect plugin {plugin_id} (OqlOS)",
            kind="oqlos",
            priority=15,
            auto_executable=True,
            scope="oqlos",
            detail="Bezpieczne odświeżenie połączenia w procesie OqlOS.",
        )
    )


def _add_tic249_device_actions(
    dev: "DeviceDiagnosis",
    status: str,
    msg: str,
    host_recover: str,
) -> None:
    if status == "ok":
        return
    if "errno 19" in msg:
        dev.issues.append("USB Tic — martwy handle po replug.")
    dev.recommended_actions.extend(
        [
            DiagnosisAction(
                id="tic249-docker-restart",
                device_id=dev.device_id,
                label="Restart hw-tic249 (Docker)",
                kind="docker",
                priority=20,
                command="docker restart hw-tic249",
                auto_executable=bool(host_recover),
                scope="host",
            ),
            DiagnosisAction(
                id="tic249-oqlos-reconnect",
                device_id=dev.device_id,
                label="Reconnect motor-tic249 plugin (OqlOS)",
                kind="oqlos",
                priority=18,
                auto_executable=True,
                scope="oqlos",
            ),
        ]
    )


def _add_dri0050_device_actions(
    dev: "DeviceDiagnosis",
    status: str,
    msg: str,
    host_recover: str,
) -> None:
    if status == "ok":
        return
    if "connection attempts failed" in msg or "503" in msg:
        dev.issues.append(
            "Sidecar DRI0050 (:8203) niedostępny lub /health=503 — OqlOS uruchomi ponownie systemd-run."
        )
    if "errno 5" in msg or "input/output error" in msg:
        dev.issues.append("Martwy handle USB RS485 pompy — odłącz/podłącz kabel pompy.")
    dev.recommended_actions.extend(
        [
            DiagnosisAction(
                id="dri0050-ensure-sidecar",
                device_id=dev.device_id,
                label="Uruchom dri0050-motor-api (OqlOS)",
                kind="oqlos",
                priority=5,
                auto_executable=True,
                scope="oqlos",
                detail="systemd-run jak make hardware-up, bez restartu całego stacku.",
            ),
            DiagnosisAction(
                id="dri0050-reconnect",
                device_id=dev.device_id,
                label="Reconnect motor-dri0050 plugin (OqlOS)",
                kind="oqlos",
                priority=18,
                auto_executable=True,
                scope="oqlos",
            ),
        ]
    )


def _diagnose_plugin_devices(
    health: "dict[str, Any]",
    adapters: "dict[str, Any]",
    platform: "dict[str, Any]",
    topology: str,
    host_recover: str,
) -> "dict[str, DeviceDiagnosis]":
    """Build per-device diagnosis for the four monitored hardware plugins."""
    devices: dict[str, DeviceDiagnosis] = {}
    for plugin_id, display_name in (
        ("modbus-io", "Waveshare Modbus IO 8CH"),
        ("modbus-adc", "Waveshare Modbus ADC 8CH"),
        ("motor-tic249", "Pololu Tic T249"),
        ("motor-dri0050", "DFRobot DRI0050"),
    ):
        entry = health.get(plugin_id) if isinstance(health.get(plugin_id), dict) else None
        adapter = adapters.get(plugin_id)
        status = _infer_status(plugin_id, entry, present=entry is not None or adapter is not None)
        dev = DeviceDiagnosis(
            device_id=plugin_id,
            display_name=display_name,
            status=status,
            health_summary=str(
                (entry or {}).get("message") or (adapter or {}).get("status") or "brak danych"
            ),
            environment={"topology": topology},
        )
        msg = _message_lower(entry)
        if plugin_id.startswith("modbus"):
            _add_modbus_device_actions(dev, plugin_id, status, msg, platform)
        elif plugin_id == "motor-tic249":
            _add_tic249_device_actions(dev, status, msg, host_recover)
        elif plugin_id == "motor-dri0050":
            _add_dri0050_device_actions(dev, status, msg, host_recover)
        devices[plugin_id] = dev
    return devices


def _build_report_global_actions(
    modbus_bad: bool,
    motors_bad: bool,
    c2004_root: str,
    host_recover: str,
) -> "list[DiagnosisAction]":
    """Build the global recovery actions for the full stack restart path."""
    global_actions: list[DiagnosisAction] = []
    if modbus_bad and motors_bad:
        global_actions.append(
            DiagnosisAction(
                id="global-stack-restart",
                device_id="*",
                label="make hardware-up",
                kind="make_target",
                priority=10,
                make_target="hardware-up",
                command=f"cd {c2004_root} && make hardware-up",
                auto_executable=bool(host_recover),
                scope="host",
            )
        )
    elif modbus_bad:
        global_actions.append(
            DiagnosisAction(
                id="global-modbus-recover",
                device_id="*",
                label="make hardware-up (Modbus)",
                kind="make_target",
                priority=12,
                make_target="hardware-up",
                command=f"cd {c2004_root} && make hardware-up",
                auto_executable=bool(host_recover),
                scope="host",
            )
        )
    return global_actions


def _resolve_host_recover() -> str:
    """Return the best available host recovery mechanism identifier."""
    return (
        os.environ.get("OQLOS_HOST_RECOVER_HOOK", "").strip()
        or os.environ.get("OQLOS_RUNTIME_CONTROL_SCRIPT", "").strip()
        or ("systemd" if shutil.which("systemctl") else "")
    )


def _diagnose_barcode_scanner(adapters: dict[str, Any]) -> DeviceDiagnosis:
    """Build barcode scanner diagnosis entry."""
    adapter = adapters.get("barcode-scanner")
    detail = (adapter or {}).get("detail") if isinstance((adapter or {}).get("detail"), dict) else {}
    present = bool(detail.get("scanner_present")) or str((adapter or {}).get("status") or "") == "ok"
    return DeviceDiagnosis(
        device_id="barcode-scanner",
        display_name="Skaner USB-HID",
        status="ok" if present else "not_present",
        health_summary="Wykryty" if present else "Brak skanera",
    )


def _build_stack_snapshot(health: dict[str, Any]) -> dict[str, Any]:
    """Call build_hardware_stack_snapshot safely, returning empty dict on error."""
    try:
        return build_hardware_stack_snapshot(health)
    except Exception:
        return {}


def build_diagnosis_report(identify: dict[str, Any]) -> DiagnosisReport:
    """Build per-device diagnosis from an identify payload (same shape as GET /identify)."""
    platform = identify.get("platform") if isinstance(identify.get("platform"), dict) else {}
    health = _health_map(identify)
    adapters = _adapter_index(identify)
    topology = str(platform.get("modbus_topology") or platform.get("modbus_topology_mode") or "").strip()
    serial_ports = [str(p) for p in (platform.get("serial_ports") or []) if p]
    host_recover = _resolve_host_recover()
    c2004_root = os.environ.get("C2004_ROOT", "/home/tom/github/maskservice/c2004")

    devices = _diagnose_plugin_devices(health, adapters, platform, topology, host_recover)
    devices["barcode-scanner"] = _diagnose_barcode_scanner(adapters)

    modbus_bad = modbus_plugins_need_repair(identify)
    motors_bad = any(devices[d].status == "error" for d in ("motor-tic249", "motor-dri0050"))
    global_actions = _build_report_global_actions(modbus_bad, motors_bad, c2004_root, host_recover)

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
    action: "DiagnosisAction",
    seen: "set[str]",
    saw_make: bool,
    motor_only: bool,
    failed: "set[str]",
) -> "tuple[bool, bool]":
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
            host.append(_action_dict(action))
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


async def _repair_dri0050_if_needed(
    targets: "list[str]",
    health_before: "dict[str, Any]",
    repairs: "list[dict[str, Any]]",
) -> None:
    """Ensure dri0050 sidecar is running if it's in the repair target list."""
    if "motor-dri0050" not in targets:
        return
    from oqlos.hardware.sidecar_control import ensure_dri0050_sidecar
    entry = health_before.get("motor-dri0050") if isinstance(health_before.get("motor-dri0050"), dict) else {}
    msg = str(entry.get("message") or "").lower()
    force = (
        "connection attempts failed" in msg
        or "http 503" in msg
        or "503" in msg
        or "connect returned false" in msg
        or not entry
    )
    repairs.append(await ensure_dri0050_sidecar(force_restart=force))


async def execute_safe_recover(gateway: Any, report: DiagnosisReport) -> dict[str, Any]:
    """Reconnect failed plugins inside OqlOS; return host_actions for sidecars."""
    repairs: list[dict[str, Any]] = []
    health_before = await gateway.health()
    targets = _recover_targets(report, health_before)
    await _repair_dri0050_if_needed(targets, health_before, repairs)
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
