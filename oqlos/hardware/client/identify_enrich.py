"""Post-process OqlOS identify payloads with steady-state labels and diagnosis hints."""

from __future__ import annotations

import os
from typing import Any

from oqlos.hardware.client.modbus_repair import rewrite_modbus_repair


def _platform_serial_ports(platform: Any) -> dict[str, str]:
    if not isinstance(platform, dict):
        return {}
    return {
        "modbus-io": str(platform.get("modbus_io_serial_port") or platform.get("modbus_bus_serial_port") or ""),
        "modbus-adc": str(platform.get("modbus_adc_serial_port") or ""),
    }


def _health_message(health: Any, probe: dict[str, Any]) -> str:
    if isinstance(health, dict):
        return str(health.get("message") or "")
    return str(probe.get("detail") or "")


def _enrich_disabled(adapter: dict, message: str) -> dict:
    """Mark adapter as disabled and set diagnosis."""
    probe = dict(adapter.get("probe") or {})
    probe["diagnosis"] = (
        message
        or "Optional peripheral — disabled in OqlOS config (use make hardware-up without HARDWARE_BENCH_MODBUS_ONLY to enable)."
    )
    adapter["status"] = "disabled"
    adapter["probe"] = probe
    return adapter


def _enrich_motor_tic249(
    adapter: dict, probe: dict, status: str, lowered: str, adapter_visible: bool
) -> dict | None:
    """Return enriched adapter dict if stale-handle condition detected, else None."""
    if not (
        ("errno 19" in lowered or "disconnected" in lowered)
        or (status in {"no-access", "error"} and adapter_visible)
    ):
        return None
    probe["diagnosis"] = (
        "USB Tic T249 visible but handle stale — unplug/replug the motor USB, "
        "then restart hw-tic249 (docker) or run: make hardware-up"
    )
    adapter["status"] = "device-stale"
    adapter["probe"] = probe
    return adapter


def _enrich_motor_dri0050(
    adapter: dict, probe: dict, status: str, lowered: str
) -> dict | None:
    """Return enriched adapter dict for dri0050 error conditions, else None."""
    if status not in {"no-access", "error"}:
        return None
    if "503" in lowered or "input/output error" in lowered or "errno 5" in lowered:
        probe["diagnosis"] = (
            "DRI0050 pump driver on :8203 cannot read serial — check /dev/ttyUSB0 cable, "
            "power, and that no other process holds the port"
        )
    adapter["probe"] = probe
    return adapter


def _enrich_modbus_adapter(
    adapter: dict, probe: dict, status: str, lowered: str, adapter_visible: bool
) -> dict | None:
    """Return enriched adapter dict for modbus serial/stale conditions, else None."""
    serial_hint = str((probe.get("local_probe") or {}).get("serial_port") or "").strip()
    stale_serial = "errno 5" in lowered or "input/output error" in lowered
    if status not in {"no-access", "error", "offline"} or not (
        adapter_visible or "timed out" in lowered or stale_serial
    ):
        return None
    if stale_serial:
        probe["diagnosis"] = (
            f"USB-RS485 path {serial_hint or 'by-id'} is configured but the open serial handle is stale "
            "(USB re-plug or tty remap, e.g. ttyACM1→ttyACM2). "
            "Restart OqlOS: make hardware-oqlos-only (or systemctl --user restart oqlos-hardware-api.service)"
        )
        adapter["status"] = "serial-stale"
    else:
        probe["diagnosis"] = (
            f"USB-RS485 adapter visible{f' at {serial_hint}' if serial_hint else ''}; "
            "Modbus module not answering — verify 24V, A/B wiring, slave ID=2, baud 9600 8N1. "
            "If OqlOS holds the port, retry after Refresh or: make hardware-modbus-probe"
        )
        adapter["status"] = "adapter-only"
    adapter["probe"] = probe
    return adapter


def enrich_adapter_entry(adapter: dict[str, Any]) -> dict[str, Any]:
    hw_id = str(adapter.get("id") or "")
    status = str(adapter.get("status") or "")
    probe = dict(adapter.get("probe") or {})
    health = probe.get("health") if isinstance(probe.get("health"), dict) else {}
    message = _health_message(health, probe)
    lowered = message.lower()

    if isinstance(health, dict) and str(health.get("status") or "").lower() == "disabled":
        return _enrich_disabled(adapter, message)

    local_probe = probe.get("local_probe") if isinstance(probe.get("local_probe"), dict) else {}
    adapter_visible = bool(local_probe.get("connected")) or bool(local_probe.get("by_id_present"))

    if hw_id == "motor-tic249":
        result = _enrich_motor_tic249(adapter, probe, status, lowered, adapter_visible)
        if result is not None:
            return result

    if hw_id == "motor-dri0050":
        result = _enrich_motor_dri0050(adapter, probe, status, lowered)
        if result is not None:
            return result

    if hw_id in {"modbus-io", "modbus-adc"}:
        result = _enrich_modbus_adapter(adapter, probe, status, lowered, adapter_visible)
        if result is not None:
            return result

    if hw_id == "rtc" and status in {"no-access", "adapter-only"}:
        probe.setdefault(
            "diagnosis",
            "piRTC sidecar reachable; DS3231 HAT absent or mock mode on desktop",
        )
        adapter["probe"] = probe

    return adapter


def _adapter_status_modbus(
    hw_id: str, status: str, lowered: str, probe: dict
) -> tuple[str, dict] | None:
    """Return (status, probe) if modbus-specific condition applies, else None."""
    if hw_id not in {"modbus-io", "modbus-adc"}:
        return None
    if "errno 5" in lowered or "input/output error" in lowered:
        probe["diagnosis"] = "USB-RS485 path is configured but the open serial handle is stale"
        return "serial-stale", probe
    if status == "adapter-only" or "serial adapter visible" in lowered:
        probe["diagnosis"] = "serial adapter visible; live Modbus response requires full scan"
        return "adapter-only", probe
    return None


def _adapter_status_tic249(
    hw_id: str, status: str, lowered: str, probe: dict
) -> tuple[str, dict] | None:
    """Return (status, probe) if tic249-specific stale-handle condition applies, else None."""
    if hw_id != "motor-tic249" or status != "error":
        return None
    if "errno 19" not in lowered and "disconnected" not in lowered:
        return None
    probe["diagnosis"] = (
        "USB device visible but handle stale — unplug/replug Tic T249, "
        "then restart the hw-tic249 sidecar on :8205"
    )
    return "device-stale", probe


def adapter_status_from_health(hw_id: str, health_entry: Any) -> tuple[str, dict[str, Any]]:
    """Map plugin health entries to identify adapter status labels."""
    if not isinstance(health_entry, dict):
        return "offline", {"connected": False, "source": "fast-health-missing"}

    status = str(health_entry.get("status") or "").lower()
    message = str(health_entry.get("message") or "")
    compatible = bool(health_entry.get("compatible"))
    probe = {"connected": compatible, "source": "fast-plugin-health", "health": health_entry}
    lowered = message.lower()

    if status == "disabled":
        probe["diagnosis"] = message or "Optional peripheral disabled in OqlOS config"
        return "disabled", probe

    modbus_result = _adapter_status_modbus(hw_id, status, lowered, probe)
    if modbus_result is not None:
        return modbus_result

    tic249_result = _adapter_status_tic249(hw_id, status, lowered, probe)
    if tic249_result is not None:
        return tic249_result

    if compatible:
        return "ok", probe
    if status == "error":
        return "no-access", probe
    return "offline", probe


def _parse_csv_ints(raw: str) -> list[int]:
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


def _ids_from_preflight(payload: dict[str, Any]) -> list[int]:
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


def _modbus_io_instance_ids(payload: dict[str, Any]) -> list[int]:
    preferred_csv = (
        os.getenv("OQLOS_MODBUS_IO_DEVICE_IDS")
        or os.getenv("MODBUS_IO_DEVICE_IDS")
        or ""
    )
    parsed = _parse_csv_ints(preferred_csv)
    if parsed:
        return list(dict.fromkeys(parsed))

    ids_from_preflight = _ids_from_preflight(payload)
    if ids_from_preflight:
        return list(dict.fromkeys(ids_from_preflight))

    single_id_raw = os.getenv("OQLOS_MODBUS_IO_DEVICE_ID", os.getenv("MODBUS_IO_DEVICE_ID", "1"))
    single_id = _parse_csv_ints(single_id_raw)
    return [single_id[0] if single_id else 1]


def _expand_modbus_io_instances(adapters: list[dict[str, Any]], payload: dict[str, Any]) -> list[dict[str, Any]]:
    instance_ids = _modbus_io_instance_ids(payload)
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


def count_detected_adapters(adapters: list[dict[str, Any]]) -> int:
    return sum(
        1
        for adapter in adapters
        if isinstance(adapter, dict)
        and adapter.get("status") in {"ok", "adapter-only", "connected"}
    )


def enrich_identify_payload(payload: dict[str, Any]) -> dict[str, Any]:
    adapters = payload.get("adapters")
    if not isinstance(adapters, list):
        return payload
    serial_ports = _platform_serial_ports(payload.get("platform"))
    normalized_adapters = []
    for entry in adapters:
        if not isinstance(entry, dict):
            normalized_adapters.append(entry)
            continue
        adapter = dict(entry)
        hw_id = str(adapter.get("id") or "")
        serial_port = serial_ports.get(hw_id)
        if serial_port and hw_id in {"modbus-io", "modbus-adc"}:
            probe = dict(adapter.get("probe") or {})
            health = probe.get("health") if isinstance(probe.get("health"), dict) else {}
            health_msg = _health_message(health, probe).lower()
            stale_serial = "errno 5" in health_msg or "input/output error" in health_msg
            local_probe = dict(probe.get("local_probe") or {})
            local_probe["serial_port"] = serial_port
            if stale_serial:
                local_probe["connected"] = False
                local_probe["by_id_present"] = True
            else:
                local_probe.setdefault("connected", True)
            probe["local_probe"] = local_probe
            adapter["probe"] = probe
        normalized_adapters.append(enrich_adapter_entry(adapter))
    payload["adapters"] = _expand_modbus_io_instances(normalized_adapters, payload)
    payload["detected"] = count_detected_adapters(payload["adapters"])
    payload["total"] = len(payload["adapters"])
    return payload


def enrich_hardware_identify(payload: dict[str, Any]) -> dict[str, Any]:
    """Apply OqlOS identify enrichment and host repair command normalization."""
    return rewrite_modbus_repair(enrich_identify_payload(payload))
