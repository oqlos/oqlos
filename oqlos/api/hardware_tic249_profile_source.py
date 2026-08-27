"""Authenticated publication of the BoardNet Tic249 device OQL profile."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from oqlos.api.hardware_configuration_routes import _require_system_role
from oqlos.errors import OqlosError
from oqlos.hardware.tic249_profile_source import (
    TIC249_CONTINUOUS_SAFE_MAX_MA,
    Tic249ProfileSourceError,
    Tic249ProfileUnavailableError,
    Tic249ProfileUnsafeError,
    apply_tic249_profile_source,
)

router = APIRouter(prefix="/hui/tic249/profile", tags=["hardware-tic249-profile"])


class Tic249ProfileSourceRequest(BaseModel):
    content: str = Field(min_length=1, max_length=256 * 1024)


@router.put("/source")
async def save_tic249_profile_source(
    payload: Tic249ProfileSourceRequest,
    x_connect_role: str | None = Header(default=None, alias="X-Connect-Role"),
) -> dict[str, Any]:
    """Program a stopped/deenergized Tic and persist the validated OQL source."""
    _require_system_role(x_connect_role)
    try:
        result = await apply_tic249_profile_source(payload.content)
    except Tic249ProfileSourceError as exc:
        raise OqlosError(
            code="api_hardware_configuration_invalid",
            status_code=422,
            message=str(exc),
            detail={
                "component": "motor-tic249",
                "stage": "profile.validate",
                "operation_id": "hardware.tic249.profile.save",
                "continuous_safe_max_ma": TIC249_CONTINUOUS_SAFE_MAX_MA,
            },
        ) from exc
    except Tic249ProfileUnsafeError as exc:
        raise OqlosError(
            code="api_hardware_configuration_invalid",
            public_code="C2004-DATA-0003",
            status_code=409,
            message=str(exc),
            detail={
                "component": "motor-tic249",
                "stage": "profile.safety",
                "operation_id": "hardware.tic249.profile.save",
            },
        ) from exc
    except (Tic249ProfileUnavailableError, OSError) as exc:
        raise OqlosError(
            code="config_unavailable",
            status_code=503,
            message=str(exc),
            detail={
                "component": "motor-tic249",
                "stage": "profile.apply",
                "operation_id": "hardware.tic249.profile.save",
            },
        ) from exc
    return {
        "ok": True,
        "persisted": True,
        "applied": True,
        "requires_service_restart": False,
        "current_measurement_available": False,
        "continuous_safe_max_ma": TIC249_CONTINUOUS_SAFE_MAX_MA,
        **result,
    }
