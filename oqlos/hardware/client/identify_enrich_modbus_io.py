"""Modbus IO multi-slave virtual adapter expansion for identify payloads."""

from __future__ import annotations

import os
from typing import Any


def parse_csv_ints(raw: str) -> list[int]:
    values: list[int] = []
    for chunk in str(raw or "").split(","):
        part = chunk.strip()
        if not part:
            continue
        try:
            values.append(int(part))
        except ValueError:
            continue
    return values


def ids_from_preflight(payload: dict[str, Any]) -> list[int]:
    """Extract modbus-io device IDs from the diagnostics preflight section."""
    diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), dict) else {}
    preflight = diagnostics.get("modbus_preflight") if isinstance(diagnostics, dict) else {}
    modules = preflight.get("modules") if isinstance(preflight, dict) else []
    ids: list[int] = []
    if not isinstance(modules, list):
        return ids
    for module in modules:
        if not isinstance(module, dict):
            continue
        if str(module.get("plugin_id") or "") != "modbus-io":
            continue
        try:
            ids.append(int(module.get("device_id")))
        except (TypeError, ValueError):
            continue
    return ids


def modbus_io_instance_ids(payload: dict[str, Any]) -> list[int]:
    preferred_csv = (
        os.getenv("OQLOS_MODBUS_IO_DEVICE_IDS")
        or os.getenv("MODBUS_IO_DEVICE_IDS")
        or ""
    )
    parsed = parse_csv_ints(preferred_csv)
    if parsed:
        return list(dict.fromkeys(parsed))

    ids_from_pref = ids_from_preflight(payload)
    if ids_from_pref:
        return list(dict.fromkeys(ids_from_pref))

    single_id_raw = os.getenv("OQLOS_MODBUS_IO_DEVICE_ID", os.getenv("MODBUS_IO_DEVICE_ID", "1"))
    single_id = parse_csv_ints(single_id_raw)
    return [single_id[0] if single_id else 1]


def expand_modbus_io_instances(adapters: list[dict[str, Any]], payload: dict[str, Any]) -> list[dict[str, Any]]:
    instance_ids = modbus_io_instance_ids(payload)
    if len(instance_ids) <= 1:
        return adapters

    has_virtual_entries = any(
        isinstance(adapter, dict) and str(adapter.get("id") or "").startswith("modbus-io-")
        for adapter in adapters
    )
    if has_virtual_entries:
        return adapters

    expanded: list[dict[str, Any]] = []
    for adapter in adapters:
        if str(adapter.get("id") or "") != "modbus-io":
            expanded.append(adapter)
            continue
        for device_id in instance_ids:
            clone = dict(adapter)
            clone["id"] = f"modbus-io-{device_id}"
            base_name = str(adapter.get("name") or "Waveshare Modbus RTU IO 8CH").strip()
            clone["name"] = f"{base_name} (slave {device_id})"
            probe = dict(clone.get("probe") or {})
            local_probe = dict(probe.get("local_probe") or {})
            local_probe.setdefault("device_id", device_id)
            probe["local_probe"] = local_probe
            clone["probe"] = probe
            expanded.append(clone)
    return expanded
