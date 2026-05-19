"""Post-process hardware identify payloads (modbus, scanner, RTC sidecar)."""

from __future__ import annotations

from typing import Any

from oqlos.hardware.modbus_identify import enrich_modbus_identify
from oqlos.hardware.rtc_probe import enrich_rtc_adapter
from oqlos.hardware.scanner_probe import enrich_scanner_adapter


def enrich_identify_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Apply platform-specific enrichment after core plugin identify."""
    if not isinstance(payload, dict):
        return payload
    payload = enrich_modbus_identify(payload)
    payload = enrich_scanner_adapter(payload)
    return enrich_rtc_adapter(payload)
