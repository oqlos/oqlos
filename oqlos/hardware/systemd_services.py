"""Whitelisted systemd service control for the C2004/OqlOS hardware node.

The hardware UI runs on the Pi where these services live. Only a fixed
whitelist of C2004/OqlOS units may be inspected or controlled — never
arbitrary systemd units — so the web surface cannot start/stop unrelated
system services.

On pi-hw the OqlOS services are ``systemctl --user`` units owned by the
``pi`` user (see redeploy/pi-hw/migration.md), so control needs **no sudo** —
a user manages their own user units. Set ``OQLOS_SYSTEMD_SCOPE=system`` to
target system units instead, in which case control uses ``sudo -n systemctl``
(and passwordless sudo must be granted, like ``host_power``).

Override the whitelist with the ``OQLOS_SYSTEMD_WHITELIST`` env var
(comma-separated unit names).
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Any

logger = logging.getLogger(__name__)

# Known C2004/OqlOS --user units on the hardware node (redeploy/pi-hw/migration.md).
_DEFAULT_WHITELIST: tuple[str, ...] = (
    "oqlos-hardware-api.service",  # OqlOS hardware runtime (:8202) — owns RS485/Modbus
    "hw-tic249.service",           # artificial-lung stepper (tic249)
    "dri0050-motor-api.service",   # pump motor (dri0050)
    "pirtc-api.service",           # RTC sidecar
    "mosquitto.service",           # MQTT broker (OQL-over-MQTT transport)
)


def _systemd_scope() -> str:
    """'user' (default, pi-hw --user units) or 'system' (sudo systemctl)."""
    return "system" if os.getenv("OQLOS_SYSTEMD_SCOPE", "user").strip().lower() == "system" else "user"


def _systemctl_argv(*args: str) -> list[str]:
    if _systemd_scope() == "system":
        return ["sudo", "-n", "systemctl", *args]
    return ["systemctl", "--user", *args]


def _journalctl_argv(*args: str) -> list[str]:
    if _systemd_scope() == "system":
        return ["journalctl", *args]
    return ["journalctl", "--user", *args]

_ALLOWED_ACTIONS: frozenset[str] = frozenset({"start", "stop", "restart", "status"})
_CONTROL_ACTIONS: frozenset[str] = frozenset({"start", "stop", "restart"})
_SHOW_TIMEOUT = 8
_CONTROL_TIMEOUT = 20
_LOG_TIMEOUT = 8
_MAX_LOG_LINES = 500

_SHOW_PROPERTIES = (
    "Id",
    "Description",
    "LoadState",
    "ActiveState",
    "SubState",
    "UnitFileState",
    "MainPID",
    "ExecMainPID",
    "ActiveEnterTimestamp",
)


def normalize_unit(unit: str) -> str:
    """Return a bare unit name as a ``*.service`` unit; leave other unit types intact."""
    name = (unit or "").strip()
    if name and "." not in name:
        name = f"{name}.service"
    return name


def service_whitelist() -> list[str]:
    """Whitelisted units, overridable via ``OQLOS_SYSTEMD_WHITELIST`` (comma-separated)."""
    raw = os.getenv("OQLOS_SYSTEMD_WHITELIST", "").strip()
    if raw:
        units = [normalize_unit(item) for item in raw.split(",") if item.strip()]
        return [u for u in units if u]
    return list(_DEFAULT_WHITELIST)


def is_whitelisted(unit: str) -> bool:
    return normalize_unit(unit) in service_whitelist()


def _systemctl_available() -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "--version"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _sudo_available() -> bool:
    try:
        result = subprocess.run(
            ["sudo", "-n", "true"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _parse_show(stdout: str) -> dict[str, str]:
    props: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            props[key.strip()] = value.strip()
    return props


def _service_status(unit: str) -> dict[str, Any]:
    """Return a status dict for a single whitelisted unit (no sudo needed)."""
    try:
        result = subprocess.run(
            _systemctl_argv(
                "show",
                unit,
                "--no-page",
                "--property=" + ",".join(_SHOW_PROPERTIES),
            ),
            capture_output=True,
            text=True,
            timeout=_SHOW_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"unit": unit, "available": False, "error": str(exc)}

    props = _parse_show(result.stdout)
    active_state = props.get("ActiveState", "unknown")
    unit_file_state = props.get("UnitFileState", "unknown")
    main_pid = props.get("MainPID") or props.get("ExecMainPID") or "0"
    try:
        pid = int(main_pid)
    except ValueError:
        pid = 0
    return {
        "unit": props.get("Id", unit),
        "available": True,
        "description": props.get("Description", ""),
        "load_state": props.get("LoadState", "unknown"),
        "active_state": active_state,
        "sub_state": props.get("SubState", "unknown"),
        "unit_file_state": unit_file_state,
        "running": active_state == "active",
        "enabled": unit_file_state == "enabled",
        "pid": pid,
        "since": props.get("ActiveEnterTimestamp", ""),
    }


def list_services() -> dict[str, Any]:
    """List status of every whitelisted unit."""
    whitelist = service_whitelist()
    if not _systemctl_available():
        return {
            "ok": False,
            "error": "systemctl unavailable — not running on a systemd host",
            "whitelist": whitelist,
            "services": [],
            "sudo": False,
        }
    services = [_service_status(unit) for unit in whitelist]
    scope = _systemd_scope()
    return {
        "ok": True,
        "scope": scope,
        "whitelist": whitelist,
        "services": services,
        "sudo": _sudo_available() if scope == "system" else True,
    }


def control_service(unit: str, action: str) -> dict[str, Any]:
    """Run a start/stop/restart/status action against a whitelisted unit."""
    normalized_unit = normalize_unit(unit)
    normalized_action = (action or "").strip().lower()

    if normalized_action not in _ALLOWED_ACTIONS:
        return {
            "ok": False,
            "unit": normalized_unit,
            "action": normalized_action,
            "error": f"Unsupported action: {action!r}",
            "allowed_actions": sorted(_ALLOWED_ACTIONS),
        }
    if not is_whitelisted(normalized_unit):
        return {
            "ok": False,
            "unit": normalized_unit,
            "action": normalized_action,
            "error": "Unit is not in the C2004/OqlOS whitelist",
            "whitelist": service_whitelist(),
        }
    if not _systemctl_available():
        return {
            "ok": False,
            "unit": normalized_unit,
            "action": normalized_action,
            "error": "systemctl unavailable — not running on a systemd host",
        }

    if normalized_action == "status":
        return {"ok": True, "unit": normalized_unit, "action": "status", "status": _service_status(normalized_unit)}

    # --user units (default): the pi user controls its own units, no sudo.
    # system scope: requires passwordless sudo for systemctl.
    if _systemd_scope() == "system" and not _sudo_available():
        return {
            "ok": False,
            "unit": normalized_unit,
            "action": normalized_action,
            "error": "Passwordless sudo unavailable — cannot control system services",
            "hint": "Grant NOPASSWD for /usr/bin/systemctl to the service user, or use --user units",
        }

    try:
        result = subprocess.run(
            _systemctl_argv(normalized_action, normalized_unit),
            capture_output=True,
            text=True,
            timeout=_CONTROL_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("systemctl %s %s failed: %s", normalized_action, normalized_unit, exc)
        return {
            "ok": False,
            "unit": normalized_unit,
            "action": normalized_action,
            "error": str(exc),
        }

    ok = result.returncode == 0
    logger.info(
        "systemctl %s %s → rc=%s", normalized_action, normalized_unit, result.returncode
    )
    return {
        "ok": ok,
        "unit": normalized_unit,
        "action": normalized_action,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "status": _service_status(normalized_unit),
    }


def service_logs(unit: str, lines: int = 100) -> dict[str, Any]:
    """Return the last ``lines`` journal entries for a whitelisted unit."""
    normalized_unit = normalize_unit(unit)
    if not is_whitelisted(normalized_unit):
        return {
            "ok": False,
            "unit": normalized_unit,
            "error": "Unit is not in the C2004/OqlOS whitelist",
        }
    try:
        count = max(1, min(int(lines), _MAX_LOG_LINES))
    except (TypeError, ValueError):
        count = 100
    try:
        result = subprocess.run(
            _journalctl_argv("-u", normalized_unit, "-n", str(count), "--no-pager", "--output=short-iso"),
            capture_output=True,
            text=True,
            timeout=_LOG_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "unit": normalized_unit, "error": str(exc)}
    if result.returncode != 0:
        return {
            "ok": False,
            "unit": normalized_unit,
            "error": result.stderr.strip() or f"journalctl exited {result.returncode}",
        }
    return {
        "ok": True,
        "unit": normalized_unit,
        "lines": count,
        "log": result.stdout.strip(),
    }


__all__ = [
    "control_service",
    "is_whitelisted",
    "list_services",
    "normalize_unit",
    "service_logs",
    "service_whitelist",
]
