"""Hardware proxy errors."""

from __future__ import annotations

from typing import Any


_DIAGNOSTIC_ISSUE_BY_PERIPHERAL = {
    "modbus-io": "hw_modbus_no_response",
    "modbus-adc": "hw_usb_adc_sidecar_unreachable",
    "piadc": "hw_usb_adc_sidecar_unreachable",
    "motor-dri0050": "hw_dri0050_sidecar_unreachable",
    "motor-tic249": "hw_tic249_sidecar_unreachable",
    "artificial-lung": "hw_tic249_sidecar_unreachable",
}


class HardwareProxyError(Exception):
    def __init__(self, status_code: int, detail: Any):
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))


def diagnostic_issue_for_peripheral(peripheral_id: str) -> str:
    """Return the granular OqlOS issue used at diagnostic HTTP boundaries."""
    normalized = str(peripheral_id or "").strip().lower().replace("_", "-")
    return _DIAGNOSTIC_ISSUE_BY_PERIPHERAL.get(normalized, "config_unavailable")


def is_oqlos_unavailable(exc: HardwareProxyError) -> bool:
    return exc.status_code in {502, 503, 504}


def oqlos_error_detail(exc: HardwareProxyError) -> tuple[str, Any]:
    detail = exc.detail
    if isinstance(detail, dict):
        message = detail.get("error") or detail.get("message") or detail.get("detail")
        return str(message or "OqlOS API unavailable"), detail
    if detail:
        return str(detail), detail
    return "OqlOS API unavailable", None
