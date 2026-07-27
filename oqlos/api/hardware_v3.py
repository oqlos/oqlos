"""Compatibility API for hardware UI moved from c2004 into OqlOS.

The browser keeps using the established ``/api/v3/hardware/*`` paths, but the
implementation is now OqlOS-owned and dispatches directly to the local hardware
gateway/plugin layer.

Split into sub-modules:
  _hw3_models.py     — request models, constants, shared helpers
  _hw3_peripheral.py — /peripheral-status, /diagnostic-command, /scanner/*
  _hw3_system.py     — /hui/*, /modbus/*, /diagnosis/*, /runtime/*, /stack/*
  _hw3_cqrs.py       — /cqrs/* audit endpoints and events WS
  hardware_configuration_routes.py — versioned OQL/YAML/JSON configuration
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from oqlos.api._hw3_cqrs import hardware_events_ws  # re-exported for main.py
from oqlos.api._hw3_cqrs import router as _cqrs_router
from oqlos.api._hw3_peripheral import sub_router as _peripheral_router
from oqlos.api._hw3_system import sub_router as _system_router
from oqlos.api.hardware_configuration_routes import router as _configuration_router

router = APIRouter(prefix="/api/v3/hardware", tags=["hardware-v3-compat"])


@router.get("/health")
async def hardware_health_v3() -> dict[str, Any]:
    from oqlos.api import hardware as hw
    payload = await hw.hardware_health()
    if isinstance(payload, dict):
        payload.setdefault("ok", payload.get("overall_ok", True))
        payload.setdefault("transport", "direct-oqlos")
    return payload


@router.get("/identify")
async def hardware_identify_v3(scan: str = "never") -> dict[str, Any]:
    from oqlos.api import hardware as hw
    return await hw.hardware_identify(scan=scan or "never")


@router.get("/proxy-info")
async def hardware_proxy_info_v3() -> dict[str, Any]:
    return {
        "ok": True,
        "transport": "direct-oqlos",
        "proxy": False,
        "service": "oqlos-hardware-api",
        "api_prefix": "/api/v3/hardware",
        "native_prefix": "/api/v1/hardware",
    }


router.include_router(_peripheral_router)
router.include_router(_system_router)
router.include_router(_cqrs_router)
router.include_router(_configuration_router)

__all__ = ["router", "hardware_events_ws"]
