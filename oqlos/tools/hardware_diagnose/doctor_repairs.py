"""Safe oqlos.yaml repair application for hardware doctor."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml

from oqlos.hardware.config_paths import resolve_oqlos_config_path
from oqlos.tools.hardware_diagnose.doctor_modbus_analysis import (
    expected_modbus_adc_params,
    expected_modbus_params,
)


def update_modbus_config(
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


def update_modbus_adc_config(
    config_path: str | Path | None,
    detected: dict[str, Any],
) -> dict[str, Any]:
    path = resolve_oqlos_config_path(config_path)
    original = path.read_text(encoding="utf-8")
    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)

    data = yaml.safe_load(original) or {}
    plugins = data.setdefault("plugins", {})
    adc = plugins.setdefault("modbus-adc", {})
    adc["enabled"] = True
    adc["connection_type"] = "modbus-rtu"
    params = adc.setdefault("connection_params", {})
    params["serial_port"] = detected["serial_port"]
    params["baudrate"] = int(detected["baudrate"])
    params["parity"] = str(detected["parity"])
    if "device_id" in detected:
        params["device_id"] = int(detected["device_id"])

    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

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
    """Apply safe doctor repairs. Currently limited to oqlos.yaml Modbus params."""
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
