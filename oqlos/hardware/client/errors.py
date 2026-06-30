"""Hardware proxy errors."""

from __future__ import annotations

from typing import Any


class HardwareProxyError(Exception):
    def __init__(self, status_code: int, detail: Any):
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))


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
