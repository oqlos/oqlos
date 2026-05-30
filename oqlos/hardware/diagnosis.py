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


def plugin_needs_repair(plugin_id: str, entry: dict[str, Any] | None) -> bool:
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


def build_diagnosis_report(identify: dict[str, Any]) -> DiagnosisReport:
    """Build per-device diagnosis from an identify payload (same shape as GET /identify)."""
    platform = identify.get("platform") if isinstance(identify.get("platform"), dict) else {}
    health = _health_map(identify)
    adapters = _adapter_index(identify)
    topology = str(platform.get("modbus_topology") or platform.get("modbus_topology_mode") or "").strip()
    serial_ports = [str(p) for p in platform.get("serial_ports") or [] if isinstance(platform.get("serial_ports"), list)]
    host_recover = (
        os.environ.get("OQLOS_HOST_RECOVER_HOOK", "").strip()
        or os.environ.get("OQLOS_RUNTIME_CONTROL_SCRIPT", "").strip()
        or ("systemd" if shutil.which("systemctl") else "")
    )
    c2004_root = os.environ.get("C2004_ROOT", "/home/tom/github/maskservice/c2004")

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
            health_summary=str((entry or {}).get("message") or (adapter or {}).get("status") or "brak danych"),
            environment={"topology": topology},
        )
        msg = _message_lower(entry)
        if plugin_id.startswith("modbus"):
            port = (
                platform.get("modbus_io_serial_port")
                if plugin_id == "modbus-io"
                else platform.get("modbus_adc_serial_port")
            )
            dev.environment["serial_port"] = port
            if status != "ok":
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
                    ),
                )
                dev.recommended_actions.append(
                    DiagnosisAction(
                        id=f"{plugin_id}-hardware-up",
                        device_id=plugin_id,
                        label="make hardware-up (host)",
                        kind="make_target",
                        priority=25,
                        make_target="hardware-up",
                        command=f"cd {c2004_root} && make hardware-up",
                        auto_executable=bool(host_recover),
                        scope="host",
                    ),
                )
        elif plugin_id == "motor-tic249" and status != "ok":
            if "errno 19" in msg:
                dev.issues.append("USB Tic — martwy handle po replug.")
            dev.recommended_actions.extend(
                [
                    DiagnosisAction(
                        id="tic249-docker-restart",
                        device_id=plugin_id,
                        label="Restart hw-tic249 (Docker)",
                        kind="docker",
                        priority=20,
                        command="docker restart hw-tic249",
                        auto_executable=bool(host_recover),
                        scope="host",
                    ),
                    DiagnosisAction(
                        id="tic249-oqlos-reconnect",
                        device_id=plugin_id,
                        label="Reconnect motor-tic249 plugin (OqlOS)",
                        kind="oqlos",
                        priority=18,
                        auto_executable=True,
                        scope="oqlos",
                    ),
                ],
            )
        elif plugin_id == "motor-dri0050" and status != "ok":
            dev.recommended_actions.extend(
                [
                    DiagnosisAction(
                        id="dri0050-restart-sidecar",
                        device_id=plugin_id,
                        label="Restart dri0050-motor-api",
                        kind="systemd",
                        priority=10,
                        command="systemctl --user restart dri0050-motor-api",
                        auto_executable=bool(host_recover),
                        scope="host",
                    ),
                    DiagnosisAction(
                        id="dri0050-restart-oqlos",
                        device_id=plugin_id,
                        label="Restart oqlos-hardware-api",
                        kind="systemd",
                        priority=15,
                        command="systemctl --user restart oqlos-hardware-api.service",
                        auto_executable=bool(host_recover),
                        scope="host",
                    ),
                    DiagnosisAction(
                        id="dri0050-reconnect",
                        device_id=plugin_id,
                        label="Reconnect motor-dri0050 plugin (OqlOS)",
                        kind="oqlos",
                        priority=18,
                        auto_executable=True,
                        scope="oqlos",
                    ),
                ],
            )
        devices[plugin_id] = dev

    adapter = adapters.get("barcode-scanner")
    detail = (adapter or {}).get("detail") if isinstance((adapter or {}).get("detail"), dict) else {}
    present = bool(detail.get("scanner_present")) or str((adapter or {}).get("status") or "") == "ok"
    devices["barcode-scanner"] = DeviceDiagnosis(
        device_id="barcode-scanner",
        display_name="Skaner USB-HID",
        status="ok" if present else "not_present",
        health_summary="Wykryty" if present else "Brak skanera",
    )

    global_actions: list[DiagnosisAction] = []
    modbus_bad = any(devices[d].status == "error" for d in ("modbus-io", "modbus-adc"))
    motors_bad = any(devices[d].status == "error" for d in ("motor-tic249", "motor-dri0050"))
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
            ),
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
            ),
        )

    error_devices = [d.device_id for d in devices.values() if d.status == "error"]
    requires_full = modbus_plugins_need_repair(identify) or modbus_bad
    snapshot: dict[str, Any] = {}
    try:
        snapshot = build_hardware_stack_snapshot(health)
    except Exception:
        snapshot = {}
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
        message="Diagnostyka: wszystkie monitorowane urządzenia OK."
        if not error_devices
        else "Diagnostyka: wymaga uwagi — " + ", ".join(error_devices),
        requires_full_stack_restart=requires_full,
    )


def _host_actions_from_report(report: DiagnosisReport) -> list[dict[str, Any]]:
    actions: list[DiagnosisAction] = list(report.global_actions)
    for dev in report.devices.values():
        actions.extend(dev.recommended_actions)
    host: list[dict[str, Any]] = []
    seen: set[str] = set()
    for action in sorted(actions, key=lambda a: (a.priority, a.id)):
        if action.scope != "host" or action.id in seen:
            continue
        seen.add(action.id)
        host.append(_action_dict(action))
    return host


async def execute_safe_recover(gateway: Any, report: DiagnosisReport) -> dict[str, Any]:
    """Reconnect failed plugins inside OqlOS; return host_actions for sidecars."""
    repairs: list[dict[str, Any]] = []
    health_before = await gateway.health()
    targets = [
        pid
        for pid in _OQLOS_SAFE_PLUGINS
        if plugin_needs_repair(pid, health_before.get(pid) if isinstance(health_before.get(pid), dict) else {})
    ]
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
        "host_actions": _host_actions_from_report(report),
        "still_failed": still_bad,
    }
