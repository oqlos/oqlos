"""Modbus configuration mismatch analysis for hardware doctor."""

from __future__ import annotations

from typing import Any

from oqlos.tools.hardware_diagnose.doctor_common import (
    Issue,
    add_issue,
    modbus_adc_config,
    modbus_config,
)
from oqlos.tools.hardware_diagnose.doctor_firmware import (
    firmware_is_remote,
    firmware_modbus_adc_health_ok,
    firmware_modbus_health_ok,
)
from oqlos.tools.hardware_diagnose.doctor_serial import owners_for_configured_port


def expected_modbus_params(modbus_probe: dict[str, Any]) -> dict[str, Any] | None:
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


def expected_modbus_adc_params(modbus_adc_probe: dict[str, Any]) -> dict[str, Any] | None:
    if not modbus_adc_probe.get("modbus_device_responds"):
        return None
    serial_port = modbus_adc_probe.get("serial_port")
    baudrate = modbus_adc_probe.get("baudrate")
    parity = modbus_adc_probe.get("parity")
    device_id = modbus_adc_probe.get("device_id")
    if not serial_port or not baudrate or not parity:
        return None
    result = {"serial_port": serial_port, "baudrate": int(baudrate), "parity": str(parity)}
    if device_id is not None:
        result["device_id"] = int(device_id)
    return result


def analyze_modbus_adc_config(detection: dict[str, Any], issues: list[Issue]) -> None:
    if firmware_is_remote(detection):
        return

    config = detection.get("config", {})
    modbus_adc_probe = detection.get("probes", {}).get("modbus_adc", {})
    expected = expected_modbus_adc_params(modbus_adc_probe)

    if not expected:
        if firmware_modbus_adc_health_ok(detection):
            return
        if modbus_adc_probe.get("connected"):
            add_issue(
                issues,
                severity="warn",
                code="modbus_adc_adapter_only",
                message=(
                    "USB serial adapter is visible, but the Modbus ADC device did "
                    "not answer. Check RS485 wiring, power, slave address and baudrate."
                ),
            )
        else:
            add_issue(
                issues,
                severity="warn",
                code="modbus_adc_not_detected",
                message=f"Modbus ADC device was not detected: {modbus_adc_probe.get('reason', 'unknown reason')}",
            )
        return

    if not config.get("ok"):
        return

    adc = modbus_adc_config(config)
    if not adc:
        add_issue(
            issues,
            severity="warn",
            code="modbus_adc_config_missing",
            message="oqlos.yaml does not define the modbus-adc plugin.",
        )
        return

    if not adc.get("enabled", True):
        add_issue(
            issues,
            severity="warn",
            code="modbus_adc_disabled_but_present",
            message=(
                f"Modbus ADC device responds on {expected['serial_port']} @ {expected['baudrate']} "
                f"8{expected['parity']}1 (device_id={expected.get('device_id', '?')}), "
                "but modbus-adc is disabled in oqlos.yaml."
            ),
            repair={
                "id": "enable_modbus_adc_config",
                "safe": True,
                "detected": expected,
            },
        )
        return

    current = adc.get("connection_params") or {}
    mismatches = {
        key: {"current": current.get(key), "detected": value}
        for key, value in expected.items()
        if current.get(key) != value
    }
    if mismatches:
        add_issue(
            issues,
            severity="error",
            code="modbus_adc_config_mismatch",
            message=(
                "oqlos.yaml Modbus ADC settings do not match the responding device "
                f"({expected['serial_port']} @ {expected['baudrate']} 8{expected['parity']}1, "
                f"device_id={expected.get('device_id', '?')})."
            ),
            repair={
                "id": "update_modbus_adc_config",
                "safe": True,
                "mismatches": mismatches,
                "detected": expected,
            },
        )


def analyze_modbus_config(detection: dict[str, Any], issues: list[Issue]) -> None:
    if firmware_is_remote(detection):
        return

    config = detection.get("config", {})
    modbus_probe = detection.get("probes", {}).get("modbus", {})
    expected = expected_modbus_params(modbus_probe)

    if not expected:
        if firmware_modbus_health_ok(detection):
            return
        if modbus_probe.get("connected"):
            add_issue(
                issues,
                severity="warn",
                code="modbus_adapter_only",
                message=(
                    "USB serial adapter is visible, but the Modbus device did "
                    "not answer. Check RS485 wiring, power, slave address and baudrate."
                ),
            )
        else:
            add_issue(
                issues,
                severity="error",
                code="modbus_not_detected",
                message=f"Modbus RTU device was not detected: {modbus_probe.get('reason', 'unknown reason')}",
            )
        return

    if not config.get("ok"):
        add_issue(
            issues,
            severity="error",
            code="config_unavailable",
            message=f"Cannot load oqlos.yaml: {config.get('error', 'unknown error')}",
        )
        return

    modbus = modbus_config(config)
    if not modbus:
        add_issue(
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
        add_issue(
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


def analyze_serial_port_owners(detection: dict[str, Any], issues: list[Issue]) -> None:
    if firmware_is_remote(detection):
        return

    host = detection.get("host", {})
    owners = host.get("serial_port_owners") if isinstance(host, dict) else {}
    if not isinstance(owners, dict) or not owners:
        return

    config = detection.get("config", {})
    modbus = modbus_config(config) if isinstance(config, dict) else None
    params = modbus.get("connection_params") if isinstance(modbus, dict) else {}
    configured_port = params.get("serial_port") if isinstance(params, dict) else None
    if not configured_port:
        return

    owner_port, proc_list = owners_for_configured_port(owners, str(configured_port))
    if not owner_port or not proc_list:
        return

    owner_labels = ", ".join(
        f"{proc.get('command', 'process')}[{proc.get('pid')}]" for proc in proc_list
    )
    port_label = str(configured_port)
    if owner_port != configured_port:
        port_label = f"{configured_port} ({owner_port})"
    add_issue(
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
