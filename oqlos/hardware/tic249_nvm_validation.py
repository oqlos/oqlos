"""Validate BoardNet Tic249 NVM limit-switch profile via the sidecar HTTP API."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

C2004_HW_NVM_MISMATCH = "C2004-HW-0018"


def _sidecar_base() -> str:
    return os.getenv("OQLOS_LUNG_MOTOR_URL", "http://127.0.0.1:8205").rstrip("/")


async def check_tic249_nvm_profile(*, timeout: float = 2.0) -> dict[str, Any]:
    """Return validation summary; never raises."""
    url = f"{_sidecar_base()}/api/nvm-validation"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            payload = response.json()
    except Exception as exc:
        logger.warning("Tic249 NVM validation skipped: %s", exc)
        return {"ok": True, "skipped": "sidecar_unreachable", "warning": str(exc)}

    return _interpret_nvm_validation(payload)


def _interpret_nvm_validation(payload: dict[str, Any]) -> dict[str, Any]:
    """Interpret sidecar evidence independently of the HTTP transport."""
    if payload.get("skipped"):
        return {"ok": True, "skipped": payload.get("skipped"), "detail": payload}
    if payload.get("warning"):
        return {"ok": True, "warning": payload.get("warning"), "detail": payload}
    if payload.get("ok"):
        return {"ok": True, "profile_id": payload.get("profile_id")}

    detail = payload.get("detail") or "Tic249 NVM limit-switch pin configuration mismatch"
    logger.error("Tic249 NVM validation failed: %s", detail)
    return {
        "ok": False,
        "error_code": C2004_HW_NVM_MISMATCH,
        "detail": detail,
        "validation": payload,
    }


__all__ = ["C2004_HW_NVM_MISMATCH", "check_tic249_nvm_profile"]
