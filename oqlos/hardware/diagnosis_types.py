"""Shared diagnosis report types and serialization."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

DeviceStatus = Literal["ok", "degraded", "error", "unknown", "skipped", "not_present"]
ActionKind = Literal["make_target", "systemd", "docker", "probe", "wizard", "manual", "http", "oqlos"]


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


def action_dict(action: DiagnosisAction) -> dict[str, Any]:
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
                "recommended_actions": [action_dict(a) for a in dev.recommended_actions],
            }
            for key, dev in report.devices.items()
        },
        "global_actions": [action_dict(a) for a in report.global_actions],
        "source": "oqlos.hardware.diagnosis",
    }
