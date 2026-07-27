"""Safe format-neutral hardware configuration repairs."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from oqlos.hardware.config_paths import resolve_oqlos_config_path
from oqlos.hardware.configuration import load_hardware_configuration, save_hardware_configuration
from oqlos.hardware.plugins.base import PluginConfig
from oqlos.tools.hardware_diagnose.doctor_modbus_analysis import (
    expected_modbus_adc_params,
    expected_modbus_params,
)


def update_modbus_config(
    config_path: str | Path | None,
    detected: dict[str, Any],
) -> dict[str, Any]:
    path = resolve_oqlos_config_path(config_path)
    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
    document = load_hardware_configuration(path)
    modbus = document.plugins.setdefault(
        "modbus-io",
        PluginConfig(plugin_id="modbus-io", enabled=True, connection_type="modbus-rtu"),
    )
    modbus.enabled = True
    modbus.connection_type = "modbus-rtu"
    params = modbus.connection_params
    params["serial_port"] = detected["serial_port"]
    params["baudrate"] = int(detected["baudrate"])
    params["parity"] = str(detected["parity"])

    save_hardware_configuration(path, document)

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


def update_modbus_adc_config(
    config_path: str | Path | None,
    detected: dict[str, Any],
) -> dict[str, Any]:
    path = resolve_oqlos_config_path(config_path)
    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
    document = load_hardware_configuration(path)
    adc = document.plugins.setdefault(
        "modbus-adc",
        PluginConfig(plugin_id="modbus-adc", enabled=True, connection_type="modbus-rtu"),
    )
    adc.enabled = True
    adc.connection_type = "modbus-rtu"
    params = adc.connection_params
    params["serial_port"] = detected["serial_port"]
    params["baudrate"] = int(detected["baudrate"])
    params["parity"] = str(detected["parity"])
    if "device_id" in detected:
        params["device_id"] = int(detected["device_id"])

    save_hardware_configuration(path, document)

    changes: dict[str, Any] = {
        "serial_port": detected["serial_port"],
        "baudrate": int(detected["baudrate"]),
        "parity": str(detected["parity"]),
    }
    if "device_id" in detected:
        changes["device_id"] = int(detected["device_id"])
    return {
        "id": "update_modbus_adc_config",
        "path": str(path),
        "backup": str(backup),
        "changes": changes,
    }


def apply_safe_fixes(
    detection: dict[str, Any],
    repairs: list[dict[str, Any]],
    *,
    config_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Apply safe Modbus repairs while preserving the active file format."""
    applied: list[dict[str, Any]] = []
    for repair in repairs:
        if not repair.get("safe"):
            continue
        repair_id = repair.get("id")
        if repair_id == "update_modbus_config":
            detected = repair.get("detected") or expected_modbus_params(
                detection.get("probes", {}).get("modbus", {})
            )
            if detected:
                applied.append(update_modbus_config(config_path, detected))
        elif repair_id in ("update_modbus_adc_config", "enable_modbus_adc_config"):
            detected = repair.get("detected") or expected_modbus_adc_params(
                detection.get("probes", {}).get("modbus_adc", {})
            )
            if detected:
                applied.append(update_modbus_adc_config(config_path, detected))
    return applied
