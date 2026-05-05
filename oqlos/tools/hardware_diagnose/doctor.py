"""Smart hardware detection and doctor-style repair suggestions."""

from __future__ import annotations

import shutil
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from oqlos.hardware.config_paths import resolve_oqlos_config_path
from oqlos.hardware.discovery import probe_waveshare_modbus
from oqlos.hardware.plugins.registry import PluginRegistry
from oqlos.tools.hardware_diagnose.discovery import (
    UsbDevice,
    list_i2c_buses,
    list_usb_serial_devices,
)
from oqlos.tools.hardware_diagnose.health import (
    check_firmware_health,
    check_firmware_identify,
)


Issue = dict[str, Any]

_HEALTH_KEYS_BY_ADAPTER = {
    "piadc": ("piadc",),
    "motor-dri0050": ("motor-dri0050", "motor"),
    "motor-tic249": ("motor-tic249", "lung"),
    "modbus-io": ("modbus-io", "modbus"),
}

_LOCAL_FIRMWARE_HOSTS = {"", "localhost", "127.0.0.1", "::1"}


def _usb_serial_only(devices: list[UsbDevice]) -> list[UsbDevice]:
    return [
        dev for dev in devices
        if dev.device.startswith(("/dev/ttyACM", "/dev/ttyUSB"))
    ]


def _load_config_summary(config_path: str | Path | None) -> dict[str, Any]:
    try:
        resolved = resolve_oqlos_config_path(config_path)
        configs = PluginRegistry.load_configs_from_yaml(resolved)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "path": str(config_path or "")}

    plugins: dict[str, dict[str, Any]] = {}
    for plugin_id, config in configs.items():
        plugins[plugin_id] = {
            "enabled": config.enabled,
            "connection_type": config.connection_type,
            "connection_params": dict(config.connection_params),
            "timeout": config.timeout,
            "retry_count": config.retry_count,
        }

    return {
        "ok": True,
        "path": str(resolved),
        "plugins": plugins,
    }


def _probe_modbus(probe_timeout: float) -> dict[str, Any]:
    capture = StringIO()
    try:
        with redirect_stdout(capture), redirect_stderr(capture):
            result = probe_waveshare_modbus(timeout=probe_timeout)
    except Exception as exc:
        result = {
            "connected": False,
            "reason": str(exc),
            "modbus_device_responds": False,
        }

    diagnostic_output = [
        line.strip() for line in capture.getvalue().splitlines()
        if line.strip()
    ]
    if diagnostic_output:
        result["diagnostic_output"] = diagnostic_output[-10:]
    return result


def _serial_port_owners(devices: list[UsbDevice]) -> dict[str, list[dict[str, str]]]:
    """Return processes currently holding detected serial devices, best effort."""
    if not shutil.which("fuser"):
        return {}

    owners: dict[str, list[dict[str, str]]] = {}
    for dev in devices:
        try:
            proc = subprocess.run(
                ["fuser", dev.device],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=1.0,
                check=False,
            )
        except Exception:
            continue

        pids = _extract_pids(f"{proc.stdout}\n{proc.stderr}")
        if not pids:
            continue
        owners[dev.device] = [_describe_pid(pid) for pid in pids]
    return owners


def _canonical_device_path(device: str) -> str:
    try:
        return str(Path(device).resolve(strict=False))
    except Exception:
        return device


def _owners_for_configured_port(
    owners: dict[str, list[dict[str, str]]],
    configured_port: str,
) -> tuple[str, list[dict[str, str]]] | tuple[None, list[dict[str, str]]]:
    if configured_port in owners:
        return configured_port, owners[configured_port]

    configured_real_path = _canonical_device_path(configured_port)
    for owner_port, proc_list in owners.items():
        if _canonical_device_path(owner_port) == configured_real_path:
            return owner_port, proc_list
    return None, []


def _extract_pids(text: str) -> list[str]:
    pids: list[str] = []
    for token in text.replace(":", " ").split():
        if token.isdigit() and token not in pids:
            pids.append(token)
    return pids


def _describe_pid(pid: str) -> dict[str, str]:
    try:
        proc = subprocess.run(
            ["ps", "-p", pid, "-o", "comm=", "-o", "args="],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=1.0,
            check=False,
        )
        line = proc.stdout.strip()
    except Exception:
        line = ""
    if not line:
        return {"pid": pid, "command": "unknown"}
    parts = line.split(None, 1)
    command = parts[0]
    args = parts[1] if len(parts) > 1 else command
    return {"pid": pid, "command": command, "args": args}


def detect_hardware(
    firmware_url: str = "http://localhost:8202",
    *,
    config_path: str | Path | None = None,
    probe_timeout: float = 0.35,
    include_firmware: bool = True,
) -> dict[str, Any]:
    """Collect local and firmware-side hardware discovery signals."""
    usb_devices = list_usb_serial_devices()
    usb_serial = _usb_serial_only(usb_devices)

    modbus_probe = _probe_modbus(probe_timeout)

    result: dict[str, Any] = {
        "config": _load_config_summary(config_path),
        "host": {
            "usb_devices": [dev.to_dict() for dev in usb_devices],
            "usb_serial_devices": [dev.to_dict() for dev in usb_serial],
            "serial_port_owners": _serial_port_owners(usb_serial),
            "i2c_buses": list_i2c_buses(),
        },
        "probes": {
            "modbus": modbus_probe,
        },
    }

    if include_firmware:
        firmware_host = _firmware_hostname(firmware_url)
        result["firmware"] = {
            "url": firmware_url,
            "host": firmware_host,
            "is_local": firmware_host in _LOCAL_FIRMWARE_HOSTS,
            "health": check_firmware_health(firmware_url),
            "identify": check_firmware_identify(firmware_url),
        }

    return result


def _firmware_hostname(firmware_url: str) -> str:
    try:
        return (urlparse(firmware_url).hostname or "").lower()
    except Exception:
        return ""


def _add_issue(
    issues: list[Issue],
    *,
    severity: str,
    code: str,
    message: str,
    repair: dict[str, Any] | None = None,
) -> None:
    issue: Issue = {
        "severity": severity,
        "code": code,
        "message": message,
    }
    if repair:
        issue["repair"] = repair
    issues.append(issue)


def _modbus_config(config: dict[str, Any]) -> dict[str, Any] | None:
    plugins = config.get("plugins")
    if not isinstance(plugins, dict):
        return None
    modbus = plugins.get("modbus-io")
    return modbus if isinstance(modbus, dict) else None


def _expected_modbus_params(modbus_probe: dict[str, Any]) -> dict[str, Any] | None:
    if not modbus_probe.get("modbus_device_responds"):
        return None
    serial_port = modbus_probe.get("serial_port")
    baudrate = modbus_probe.get("baudrate")
    parity = modbus_probe.get("parity")
    if not serial_port or not baudrate or not parity:
        return None
    return {
        "serial_port": serial_port,
        "baudrate": int(baudrate),
        "parity": str(parity),
    }


def _analyze_modbus_config(detection: dict[str, Any], issues: list[Issue]) -> None:
    if _firmware_is_remote(detection):
        return

    config = detection.get("config", {})
    modbus_probe = detection.get("probes", {}).get("modbus", {})
    expected = _expected_modbus_params(modbus_probe)

    if not expected:
        if _firmware_modbus_health_ok(detection):
            return
        if modbus_probe.get("connected"):
            _add_issue(
                issues,
                severity="warn",
                code="modbus_adapter_only",
                message=(
                    "USB serial adapter is visible, but the Modbus device did "
                    "not answer. Check RS485 wiring, power, slave address and baudrate."
                ),
            )
        else:
            _add_issue(
                issues,
                severity="error",
                code="modbus_not_detected",
                message=f"Modbus RTU device was not detected: {modbus_probe.get('reason', 'unknown reason')}",
            )
        return

    if not config.get("ok"):
        _add_issue(
            issues,
            severity="error",
            code="config_unavailable",
            message=f"Cannot load oqlos.yaml: {config.get('error', 'unknown error')}",
        )
        return

    modbus = _modbus_config(config)
    if not modbus:
        _add_issue(
            issues,
            severity="error",
            code="modbus_config_missing",
            message="oqlos.yaml does not define the modbus-io plugin.",
        )
        return

    current = modbus.get("connection_params") or {}
    mismatches = {
        key: {"current": current.get(key), "detected": value}
        for key, value in expected.items()
        if current.get(key) != value
    }
    if mismatches:
        _add_issue(
            issues,
            severity="error",
            code="modbus_config_mismatch",
            message=(
                "oqlos.yaml Modbus settings do not match the responding device "
                f"({expected['serial_port']} @ {expected['baudrate']} 8{expected['parity']}1)."
            ),
            repair={
                "id": "update_modbus_config",
                "safe": True,
                "mismatches": mismatches,
                "detected": expected,
            },
        )


def _analyze_firmware_access(detection: dict[str, Any], issues: list[Issue]) -> None:
    firmware = detection.get("firmware")
    if not isinstance(firmware, dict):
        return

    health = firmware.get("health") or {}
    identify = firmware.get("identify") or {}
    host_serial = detection.get("host", {}).get("usb_serial_devices") or []

    if "error" in health:
        _add_issue(
            issues,
            severity="error",
            code="firmware_unreachable",
            message=f"Firmware health endpoint is unavailable: {health['error']}",
            repair={
                "id": "start_firmware",
                "safe": False,
                "hint": "Start oqlos-server or the hardware docker compose stack.",
            },
        )
        return

    mode = str(health.get("mode", "unknown")).lower()
    if mode and mode != "real":
        _add_issue(
            issues,
            severity="warn",
            code="firmware_not_real",
            message=f"Firmware reports mode={mode!r}; actuator endpoints will not control real hardware.",
            repair={
                "id": "enable_real_mode",
                "safe": False,
                "hint": (
                    "Restart firmware with HARDWARE_MODE=real or "
                    "OQLOS_HARDWARE_MODE=real. This is not applied by --fix "
                    "because it changes runtime actuator behavior."
                ),
            },
        )

    if "error" in identify:
        _add_issue(
            issues,
            severity="warn",
            code="identify_unavailable",
            message=f"Firmware identify endpoint is unavailable: {identify['error']}",
        )
        return

    diagnostics = identify.get("diagnostics") if isinstance(identify, dict) else {}
    firmware_serial = []
    if isinstance(diagnostics, dict):
        firmware_serial = diagnostics.get("serial_ports") or []

    if host_serial and not firmware_serial:
        serial_mounts = ", ".join(str(dev.get("device")) for dev in host_serial if dev.get("device"))
        if not firmware.get("is_local", True):
            firmware_host = firmware.get("host") or firmware.get("url") or "remote host"
            _add_issue(
                issues,
                severity="warn",
                code="remote_firmware_no_serial_access",
                message=(
                    "The CLI host sees USB serial devices, but firmware is running on "
                    f"{firmware_host}; remote firmware cannot access local /dev/ttyACM* "
                    "or /dev/ttyUSB* devices."
                ),
                repair={
                    "id": "align_firmware_host",
                    "safe": False,
                    "hint": (
                        "Attach the USB/serial hardware to the firmware host, run firmware "
                        "on this machine, or configure firmware to call network-reachable "
                        "hardware services instead of local /dev devices."
                    ),
                },
            )
        else:
            _add_issue(
                issues,
                severity="warn",
                code="firmware_no_serial_access",
                message=(
                    "Host sees USB serial devices, but firmware identify sees none. "
                    "The service is probably missing /dev/ttyACM* or /dev/ttyUSB* device mounts."
                ),
                repair={
                    "id": "mount_serial_devices",
                    "safe": False,
                    "hint": (
                        "Mount detected serial devices into the firmware container "
                        f"({serial_mounts}) or run firmware on the host; then restart firmware."
                    ),
                },
            )

    adapters = identify.get("adapters") if isinstance(identify, dict) else []
    if isinstance(adapters, list):
        for adapter in adapters:
            status = adapter.get("status")
            adapter_id = adapter.get("id", "unknown")
            health_status = _adapter_health_status(health, adapter_id)
            if health_status is not None:
                if _health_status_is_ok(health_status):
                    continue
                _add_issue(
                    issues,
                    severity="warn",
                    code=f"adapter_{adapter_id}_health_not_ok",
                    message=f"Firmware adapter {adapter_id} health is {health_status}.",
                )
                continue
            if status not in (None, "ok"):
                _add_issue(
                    issues,
                    severity="warn",
                    code=f"adapter_{adapter_id}_not_ok",
                    message=f"Firmware adapter {adapter_id} status is {status}.",
                )


def _adapter_health_status(health: dict[str, Any], adapter_id: str) -> Any | None:
    keys = _HEALTH_KEYS_BY_ADAPTER.get(adapter_id, (adapter_id,))
    for key in keys:
        if key in health:
            return health[key]
    return None


def _health_status_is_ok(raw_status: Any) -> bool:
    if isinstance(raw_status, dict):
        status = str(raw_status.get("status", "")).lower()
        compatible = raw_status.get("compatible")
        return status in {"ok", "connected"} and compatible is not False

    status = str(raw_status).lower()
    if not status:
        return False
    if status == "ok" or status.startswith("ok "):
        return True
    if status in {"connected", "healthy", "ready"}:
        return True
    if status.startswith(("connected ", "healthy ", "ready ")):
        return True
    if "error" in status or "offline" in status or "no-access" in status:
        return False
    return False


def _analyze_serial_port_owners(detection: dict[str, Any], issues: list[Issue]) -> None:
    if _firmware_is_remote(detection):
        return

    host = detection.get("host", {})
    owners = host.get("serial_port_owners") if isinstance(host, dict) else {}
    if not isinstance(owners, dict) or not owners:
        return

    config = detection.get("config", {})
    modbus = _modbus_config(config) if isinstance(config, dict) else None
    params = modbus.get("connection_params") if isinstance(modbus, dict) else {}
    configured_port = params.get("serial_port") if isinstance(params, dict) else None
    if not configured_port:
        return

    owner_port, proc_list = _owners_for_configured_port(owners, str(configured_port))
    if not owner_port or not proc_list:
        return

    owner_labels = ", ".join(
        f"{proc.get('command', 'process')}[{proc.get('pid')}]" for proc in proc_list
    )
    port_label = str(configured_port)
    if owner_port != configured_port:
        port_label = f"{configured_port} ({owner_port})"
    _add_issue(
        issues,
        severity="warn",
        code="serial_port_busy",
        message=(
            f"Configured Modbus port {port_label} is already open by {owner_labels}. "
            "Only one process can own a Modbus RTU serial port at a time."
        ),
        repair={
            "id": "release_serial_port",
            "safe": False,
            "hint": (
                f"Stop the process using {owner_port}, or point oqlctl to that "
                "already-running firmware URL instead of probing the same serial port twice."
            ),
        },
    )


def _collect_repairs(issues: list[Issue]) -> list[dict[str, Any]]:
    repairs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for issue in issues:
        repair = issue.get("repair")
        if not isinstance(repair, dict):
            continue
        repair_id = str(repair.get("id", ""))
        if not repair_id or repair_id in seen:
            continue
        seen.add(repair_id)
        repairs.append({"applied": False, **repair})
    return repairs


def build_doctor_report(
    firmware_url: str = "http://localhost:8202",
    *,
    config_path: str | Path | None = None,
    probe_timeout: float = 0.35,
    fix: bool = False,
) -> dict[str, Any]:
    """Run smart detection, analyze problems, and optionally apply safe fixes."""
    detection = detect_hardware(
        firmware_url,
        config_path=config_path,
        probe_timeout=probe_timeout,
        include_firmware=True,
    )
    issues: list[Issue] = []
    _analyze_modbus_config(detection, issues)
    _analyze_serial_port_owners(detection, issues)
    _analyze_firmware_access(detection, issues)

    repairs = _collect_repairs(issues)
    applied: list[dict[str, Any]] = []
    if fix:
        applied = apply_safe_fixes(detection, repairs, config_path=config_path)
        for repair in repairs:
            if any(item.get("id") == repair.get("id") for item in applied):
                repair["applied"] = True

    error_count = sum(1 for issue in issues if issue["severity"] == "error")
    warn_count = sum(1 for issue in issues if issue["severity"] == "warn")
    return {
        "ok": error_count == 0,
        "status": "ok" if error_count == 0 and warn_count == 0 else "needs_attention",
        "summary": {
            "errors": error_count,
            "warnings": warn_count,
            "repairs": len(repairs),
            "applied_repairs": len(applied),
        },
        "detection": detection,
        "issues": issues,
        "repairs": repairs,
        "applied_repairs": applied,
        "fix_requested": fix,
    }


def apply_safe_fixes(
    detection: dict[str, Any],
    repairs: list[dict[str, Any]],
    *,
    config_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Apply safe doctor repairs. Currently limited to oqlos.yaml Modbus params."""
    applied: list[dict[str, Any]] = []
    for repair in repairs:
        if repair.get("id") != "update_modbus_config" or not repair.get("safe"):
            continue
        detected = repair.get("detected") or _expected_modbus_params(
            detection.get("probes", {}).get("modbus", {})
        )
        if not detected:
            continue
        applied.append(_update_modbus_config(config_path, detected))
    return applied


def _update_modbus_config(
    config_path: str | Path | None,
    detected: dict[str, Any],
) -> dict[str, Any]:
    path = resolve_oqlos_config_path(config_path)
    original = path.read_text(encoding="utf-8")
    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)

    data = yaml.safe_load(original) or {}
    plugins = data.setdefault("plugins", {})
    modbus = plugins.setdefault("modbus-io", {})
    modbus.setdefault("enabled", True)
    modbus["connection_type"] = "modbus-rtu"
    params = modbus.setdefault("connection_params", {})
    params["serial_port"] = detected["serial_port"]
    params["baudrate"] = int(detected["baudrate"])
    params["parity"] = str(detected["parity"])

    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    return {
        "id": "update_modbus_config",
        "path": str(path),
        "backup": str(backup),
        "changes": {
            "serial_port": detected["serial_port"],
            "baudrate": int(detected["baudrate"]),
            "parity": str(detected["parity"]),
        },
    }


def format_detection(detection: dict[str, Any]) -> str:
    """Format smart detection output for operators."""
    lines = ["", "OqlOS Smart Detect", "-" * 50]
    firmware = detection.get("firmware")
    if isinstance(firmware, dict):
        location = "local" if firmware.get("is_local", True) else f"remote host {firmware.get('host')}"
        lines.append(f"Firmware: {firmware.get('url')} ({location})")
    host = detection.get("host", {})
    serial = host.get("usb_serial_devices") or []
    lines.append(f"Host USB serial devices: {len(serial)}")
    for dev in serial:
        label = dev.get("product") or dev.get("description") or "USB serial"
        lines.append(f"  - {dev.get('device')}: {label}")

    buses = host.get("i2c_buses") or []
    lines.append(f"I2C buses: {', '.join(buses) if buses else 'none'}")

    modbus = detection.get("probes", {}).get("modbus", {})
    if _firmware_is_remote(detection):
        lines.append(f"Modbus: remote firmware status {_firmware_adapter_status(detection, 'modbus-io') or 'unknown'}")
    elif modbus.get("modbus_device_responds"):
        lines.append(
            "Modbus: OK "
            f"{modbus.get('serial_port')} @ {modbus.get('baudrate')} 8{modbus.get('parity')}1"
        )
    elif _firmware_modbus_health_ok(detection):
        lines.append("Modbus: OK via firmware (local serial port is already in use)")
    else:
        lines.append(f"Modbus: not ready ({modbus.get('reason') or modbus.get('note') or 'no response'})")

    config = detection.get("config", {})
    lines.append(f"Config: {config.get('path') if config.get('ok') else config.get('error')}")
    return "\n".join(lines)


def _firmware_modbus_health_ok(detection: dict[str, Any]) -> bool:
    firmware = detection.get("firmware")
    if not isinstance(firmware, dict):
        return False
    health = firmware.get("health")
    if not isinstance(health, dict):
        return False
    status = _adapter_health_status(health, "modbus-io")
    if isinstance(status, dict):
        return _health_status_is_ok(status)
    if isinstance(status, str) and status.lower().startswith(("ok", "connected", "healthy", "ready")):
        return True

    identify = firmware.get("identify")
    adapters = identify.get("adapters") if isinstance(identify, dict) else []
    if isinstance(adapters, list):
        for adapter in adapters:
            if adapter.get("id") == "modbus-io":
                return adapter.get("status") == "ok"
    return False


def _firmware_is_remote(detection: dict[str, Any]) -> bool:
    firmware = detection.get("firmware")
    return isinstance(firmware, dict) and firmware.get("is_local") is False


def _firmware_adapter_status(detection: dict[str, Any], adapter_id: str) -> str | None:
    firmware = detection.get("firmware")
    identify = firmware.get("identify") if isinstance(firmware, dict) else None
    adapters = identify.get("adapters") if isinstance(identify, dict) else None
    if not isinstance(adapters, list):
        return None
    for adapter in adapters:
        if adapter.get("id") == adapter_id:
            status = adapter.get("status")
            return str(status) if status is not None else None
    return None


def format_doctor(report: dict[str, Any]) -> str:
    """Format a doctor report for operators."""
    lines = ["", "OqlOS Doctor", "-" * 50]
    summary = report.get("summary", {})
    lines.append(
        "Status: "
        f"{report.get('status')} "
        f"({summary.get('errors', 0)} errors, {summary.get('warnings', 0)} warnings)"
    )

    lines.append(format_detection(report.get("detection", {})).strip())
    issues = report.get("issues") or []
    if not issues:
        lines.append("[OK] No issues found.")
    else:
        lines.append("")
        lines.append("Issues:")
        for issue in issues:
            severity = str(issue.get("severity", "info")).upper()
            lines.append(f"  [{severity}] {issue.get('code')}: {issue.get('message')}")
            repair = issue.get("repair")
            if isinstance(repair, dict) and repair.get("hint"):
                lines.append(f"        fix: {repair['hint']}")

    applied = report.get("applied_repairs") or []
    if applied:
        lines.append("")
        lines.append("Applied repairs:")
        for repair in applied:
            lines.append(f"  - {repair.get('id')} -> {repair.get('path')}")
            if repair.get("backup"):
                lines.append(f"    backup: {repair['backup']}")

    repairs = report.get("repairs") or []
    if report.get("fix_requested") and repairs:
        unapplied = [
            repair for repair in repairs
            if not any(item.get("id") == repair.get("id") for item in applied)
        ]
        if unapplied:
            lines.append("")
            lines.append("Unapplied repairs:")
            for repair in unapplied:
                safety = "manual/unsafe" if not repair.get("safe") else "safe"
                lines.append(f"  - skipped {safety}: {repair.get('id')}")
                if repair.get("hint"):
                    lines.append(f"    hint: {repair['hint']}")

    return "\n".join(lines)
