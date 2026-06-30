"""httpx response parsing helpers."""

from __future__ import annotations

from typing import Any

import httpx


def safe_response_payload(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text or None


def response_error_message(payload: Any) -> str:
    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("error") or payload.get("message")
        if isinstance(detail, dict):
            return str(detail.get("error") or detail.get("message") or detail)
        if detail:
            return str(detail)
    if isinstance(payload, str) and payload:
        return payload
    return ""
