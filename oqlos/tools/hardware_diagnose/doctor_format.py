"""Human-readable formatting for hardware doctor reports."""

from __future__ import annotations

from typing import Any

from oqlos.tools.hardware_diagnose.doctor_firmware import (
    firmware_adapter_status,
    firmware_is_remote,
    firmware_modbus_health_ok,
)


def format_modbus_status(detection: dict[str, Any]) -> str:
    """Format the Modbus probe status line."""
    modbus = detection.get("probes", {}).get("modbus", {})
    if firmware_is_remote(detection):
        status = firmware_adapter_status(detection, "modbus-io") or "unknown"
        return f"Modbus: remote firmware status {status}"
    if modbus.get("modbus_device_responds"):
        return (
            "Modbus: OK "
            f"{modbus.get('serial_port')} @ {modbus.get('baudrate')} 8{modbus.get('parity')}1"
        )
    if firmware_modbus_health_ok(detection):
        return "Modbus: OK via firmware (local serial port is already in use)"
    return f"Modbus: not ready ({modbus.get('reason') or modbus.get('note') or 'no response'})"


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
    lines.append(format_modbus_status(detection))
    config = detection.get("config", {})
    lines.append(f"Config: {config.get('path') if config.get('ok') else config.get('error')}")
    return "\n".join(lines)


def _format_doctor_issues(issues: list) -> list[str]:
    """Format the issues section of the doctor report."""
    if not issues:
        return ["[OK] No issues found."]
    lines = ["", "Issues:"]
    for issue in issues:
        severity = str(issue.get("severity", "info")).upper()
        lines.append(f"  [{severity}] {issue.get('code')}: {issue.get('message')}")
        repair = issue.get("repair")
        if isinstance(repair, dict) and repair.get("hint"):
            lines.append(f"        fix: {repair['hint']}")
    return lines


def _format_doctor_applied_repairs(applied: list) -> list[str]:
    """Format the applied repairs section."""
    if not applied:
        return []
    lines = ["", "Applied repairs:"]
    for repair in applied:
        lines.append(f"  - {repair.get('id')} -> {repair.get('path')}")
        if repair.get("backup"):
            lines.append(f"    backup: {repair['backup']}")
    return lines


def _format_doctor_unapplied(repairs: list, applied: list) -> list[str]:
    """Format the unapplied repairs section."""
    unapplied = [
        r for r in repairs
        if not any(item.get("id") == r.get("id") for item in applied)
    ]
    if not unapplied:
        return []
    lines = ["", "Unapplied repairs:"]
    for repair in unapplied:
        safety = "manual/unsafe" if not repair.get("safe") else "safe"
        lines.append(f"  - skipped {safety}: {repair.get('id')}")
        if repair.get("hint"):
            lines.append(f"    hint: {repair['hint']}")
    return lines


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
    lines.extend(_format_doctor_issues(report.get("issues") or []))
    lines.extend(_format_doctor_applied_repairs(report.get("applied_repairs") or []))
    if report.get("fix_requested") and report.get("repairs"):
        lines.extend(_format_doctor_unapplied(report["repairs"], report.get("applied_repairs") or []))
    return "\n".join(lines)
