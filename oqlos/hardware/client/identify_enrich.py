"""Post-process OqlOS identify payloads with steady-state labels and diagnosis hints."""

from __future__ import annotations

from typing import Any

from oqlos.hardware.client.identify_enrich_adapters import (
    adapter_status_from_health,
    enrich_adapter_entry,
    health_message,
)

# Backward-compatible re-exports
__all__ = [
    "adapter_status_from_health",
    "enrich_adapter_entry",
    "enrich_hardware_identify",
    "enrich_identify_payload",
]
from oqlos.hardware.client.identify_enrich_modbus_io import expand_modbus_io_instances
from oqlos.hardware.client.modbus_repair import rewrite_modbus_repair


def _platform_serial_ports(platform: Any) -> dict[str, str]:
    if not isinstance(platform, dict):
        return {}
    return {
        "modbus-io": str(platform.get("modbus_io_serial_port") or platform.get("modbus_bus_serial_port") or ""),
        "modbus-adc": str(platform.get("modbus_adc_serial_port") or ""),
    }


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
            health_msg = health_message(health, probe).lower()
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
    payload["adapters"] = expand_modbus_io_instances(normalized_adapters, payload)
    payload["detected"] = count_detected_adapters(payload["adapters"])
    payload["total"] = len(payload["adapters"])
    return payload


def enrich_hardware_identify(payload: dict[str, Any]) -> dict[str, Any]:
    """Apply OqlOS identify enrichment and host repair command normalization."""
    return rewrite_modbus_repair(enrich_identify_payload(payload))
