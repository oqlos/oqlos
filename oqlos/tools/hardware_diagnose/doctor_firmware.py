"""Firmware-side health interpretation for hardware doctor."""

from __future__ import annotations

from typing import Any

from oqlos.hardware.health_status import health_status_is_ok
from oqlos.tools.hardware_diagnose.doctor_common import (
    Issue,
    _HEALTH_KEYS_BY_ADAPTER,
    add_issue,
)


def adapter_health_status(health: dict[str, Any], adapter_id: str) -> Any | None:
    keys = _HEALTH_KEYS_BY_ADAPTER.get(adapter_id, (adapter_id,))
    for key in keys:
        if key in health:
            return health[key]
    return None


def firmware_is_remote(detection: dict[str, Any]) -> bool:
    firmware = detection.get("firmware")
    return isinstance(firmware, dict) and firmware.get("is_local") is False


def firmware_adapter_status(detection: dict[str, Any], adapter_id: str) -> str | None:
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


def firmware_modbus_health_ok(detection: dict[str, Any]) -> bool:
    firmware = detection.get("firmware")
    if not isinstance(firmware, dict):
        return False
    health = firmware.get("health")
    if not isinstance(health, dict):
        return False
    status = adapter_health_status(health, "modbus-io")
    if isinstance(status, dict):
        return health_status_is_ok(status)
    if isinstance(status, str) and status.lower().startswith(("ok", "connected", "healthy", "ready")):
        return True

    identify = firmware.get("identify")
    adapters = identify.get("adapters") if isinstance(identify, dict) else []
    if isinstance(adapters, list):
        for adapter in adapters:
            if adapter.get("id") == "modbus-io":
                return adapter.get("status") == "ok"
    return False


def firmware_modbus_adc_health_ok(detection: dict[str, Any]) -> bool:
    firmware = detection.get("firmware") or {}
    health = firmware.get("health") or {}
    adc_health = health.get("modbus-adc")
    if isinstance(adc_health, dict):
        return bool(adc_health.get("compatible"))
    return False


def check_firmware_health_error(firmware: dict[str, Any], issues: list[Issue]) -> bool:
    """Check if firmware health endpoint is unreachable. Returns True if fatal."""
    health = firmware.get("health") or {}
    if "error" not in health:
        return False
    add_issue(
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
    return True


def check_firmware_mode(health: dict[str, Any], issues: list[Issue]) -> None:
    """Warn if firmware is not in 'real' mode."""
    mode = str(health.get("mode", "unknown")).lower()
    if not mode or mode == "real":
        return
    add_issue(
        issues,
        severity="warn",
        code="firmware_not_real",
        message=(
            f"Firmware reports mode={mode!r}; actuator endpoints will not control real hardware."
        ),
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


def check_firmware_serial_access(
    firmware: dict[str, Any],
    host_serial: list,
    issues: list[Issue],
    identify: dict[str, Any],
) -> None:
    """Warn if host sees serial devices but firmware cannot."""
    diagnostics = identify.get("diagnostics") if isinstance(identify, dict) else {}
    firmware_serial: list = []
    if isinstance(diagnostics, dict):
        firmware_serial = diagnostics.get("serial_ports") or []
    if not host_serial or firmware_serial:
        return
    serial_mounts = ", ".join(
        str(dev.get("device")) for dev in host_serial if dev.get("device")
    )
    if not firmware.get("is_local", True):
        firmware_host = firmware.get("host") or firmware.get("url") or "remote host"
        add_issue(
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
        add_issue(
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


def check_firmware_adapters(
    identify: dict[str, Any], health: dict[str, Any], issues: list[Issue]
) -> None:
    """Check each firmware adapter's health status."""
    adapters = identify.get("adapters") if isinstance(identify, dict) else []
    if not isinstance(adapters, list):
        return
    for adapter in adapters:
        status = adapter.get("status")
        adapter_id = adapter.get("id", "unknown")
        health_status = adapter_health_status(health, adapter_id)
        if health_status is not None:
            if health_status_is_ok(health_status):
                continue
            add_issue(
                issues,
                severity="warn",
                code=f"adapter_{adapter_id}_health_not_ok",
                message=f"Firmware adapter {adapter_id} health is {health_status}.",
            )
            continue
        if status not in (None, "ok"):
            add_issue(
                issues,
                severity="warn",
                code=f"adapter_{adapter_id}_not_ok",
                message=f"Firmware adapter {adapter_id} status is {status}.",
            )


def analyze_firmware_access(detection: dict[str, Any], issues: list[Issue]) -> None:
    firmware = detection.get("firmware")
    if not isinstance(firmware, dict):
        return

    health = firmware.get("health") or {}
    identify = firmware.get("identify") or {}
    host_serial = detection.get("host", {}).get("usb_serial_devices") or []

    if check_firmware_health_error(firmware, issues):
        return

    check_firmware_mode(health, issues)

    if "error" in identify:
        add_issue(
            issues,
            severity="warn",
            code="identify_unavailable",
            message=f"Firmware identify endpoint is unavailable: {identify['error']}",
        )
        return

    check_firmware_serial_access(firmware, host_serial, issues, identify)
    check_firmware_adapters(identify, health, issues)
