"""Smart hardware detection and doctor-style repair suggestions."""

from __future__ import annotations

import shutil
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

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
            "i2c_buses": list_i2c_buses(),
        },
        "probes": {
            "modbus": modbus_probe,
        },
    }

    if include_firmware:
        result["firmware"] = {
            "url": firmware_url,
            "health": check_firmware_health(firmware_url),
            "identify": check_firmware_identify(firmware_url),
        }

    return result


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
    config = detection.get("config", {})
    modbus_probe = detection.get("probes", {}).get("modbus", {})
    expected = _expected_modbus_params(modbus_probe)

    if not expected:
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
                "hint": "Run firmware with HARDWARE_MODE=real or OQLOS_HARDWARE_MODE=real.",
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
                "hint": "Mount the detected serial device into the firmware container or run firmware on the host.",
            },
        )

    adapters = identify.get("adapters") if isinstance(identify, dict) else []
    if isinstance(adapters, list):
        for adapter in adapters:
            status = adapter.get("status")
            adapter_id = adapter.get("id", "unknown")
            if status not in (None, "ok"):
                _add_issue(
                    issues,
                    severity="warn",
                    code=f"adapter_{adapter_id}_not_ok",
                    message=f"Firmware adapter {adapter_id} status is {status}.",
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
    host = detection.get("host", {})
    serial = host.get("usb_serial_devices") or []
    lines.append(f"Host USB serial devices: {len(serial)}")
    for dev in serial:
        label = dev.get("product") or dev.get("description") or "USB serial"
        lines.append(f"  - {dev.get('device')}: {label}")

    buses = host.get("i2c_buses") or []
    lines.append(f"I2C buses: {', '.join(buses) if buses else 'none'}")

    modbus = detection.get("probes", {}).get("modbus", {})
    if modbus.get("modbus_device_responds"):
        lines.append(
            "Modbus: OK "
            f"{modbus.get('serial_port')} @ {modbus.get('baudrate')} 8{modbus.get('parity')}1"
        )
    else:
        lines.append(f"Modbus: not ready ({modbus.get('reason') or modbus.get('note') or 'no response'})")

    config = detection.get("config", {})
    lines.append(f"Config: {config.get('path') if config.get('ok') else config.get('error')}")
    return "\n".join(lines)


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

    return "\n".join(lines)
