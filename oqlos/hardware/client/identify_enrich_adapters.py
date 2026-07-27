"""Per-adapter identify enrichment and fast-health status mapping."""

from __future__ import annotations

from typing import Any


def health_message(health: Any, probe: dict[str, Any]) -> str:
    if isinstance(health, dict):
        return str(health.get("message") or "")
    return str(probe.get("detail") or "")


def enrich_disabled(adapter: dict, message: str) -> dict:
    """Mark adapter as disabled and set diagnosis."""
    probe = dict(adapter.get("probe") or {})
    probe["diagnosis"] = (
        message
        or "Optional peripheral — disabled in OqlOS config (use make hardware-up without HARDWARE_BENCH_MODBUS_ONLY to enable)."
    )
    adapter["status"] = "disabled"
    adapter["probe"] = probe
    return adapter


def enrich_motor_tic249(
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


def enrich_motor_dri0050(
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


def enrich_modbus_adapter(
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
            "Modbus module not answering — verify 24V, A/B wiring, slave ID=2, baud 4800 8N1. "
            "If OqlOS holds the port, retry after Refresh or: make hardware-modbus-probe"
        )
        adapter["status"] = "adapter-only"
    adapter["probe"] = probe
    return adapter


def enrich_by_device_id(
    hw_id: str,
    adapter: dict,
    probe: dict,
    status: str,
    lowered: str,
    adapter_visible: bool,
) -> dict | None:
    """Dispatch to the per-device enricher; return enriched adapter or None."""
    if hw_id == "motor-tic249":
        return enrich_motor_tic249(adapter, probe, status, lowered, adapter_visible)
    if hw_id == "motor-dri0050":
        return enrich_motor_dri0050(adapter, probe, status, lowered)
    if hw_id in {"modbus-io", "modbus-adc"}:
        return enrich_modbus_adapter(adapter, probe, status, lowered, adapter_visible)
    return None


def enrich_adapter_entry(adapter: dict[str, Any]) -> dict[str, Any]:
    hw_id = str(adapter.get("id") or "")
    status = str(adapter.get("status") or "")
    probe = dict(adapter.get("probe") or {})
    health = probe.get("health") if isinstance(probe.get("health"), dict) else {}
    message = health_message(health, probe)
    lowered = message.lower()

    if isinstance(health, dict) and str(health.get("status") or "").lower() == "disabled":
        return enrich_disabled(adapter, message)

    local_probe = probe.get("local_probe") if isinstance(probe.get("local_probe"), dict) else {}
    adapter_visible = bool(local_probe.get("connected")) or bool(local_probe.get("by_id_present"))

    device_result = enrich_by_device_id(hw_id, adapter, probe, status, lowered, adapter_visible)
    if device_result is not None:
        return device_result

    if hw_id == "rtc" and status in {"no-access", "adapter-only"}:
        probe.setdefault(
            "diagnosis",
            "piRTC sidecar reachable; DS3231 HAT absent or mock mode on desktop",
        )
        adapter["probe"] = probe

    return adapter


def adapter_status_modbus(
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


def adapter_status_tic249(
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

    modbus_result = adapter_status_modbus(hw_id, status, lowered, probe)
    if modbus_result is not None:
        return modbus_result

    tic249_result = adapter_status_tic249(hw_id, status, lowered, probe)
    if tic249_result is not None:
        return tic249_result

    if compatible:
        return "ok", probe
    if status == "error":
        return "no-access", probe
    return "offline", probe
