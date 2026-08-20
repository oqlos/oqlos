"""Authenticated publication of the live HUI OQL profile."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from oqlos.api.hardware_configuration_routes import (
    _configuration_unavailable,
    _require_system_role,
)
from oqlos.errors import OqlosError
from oqlos.hardware.hui_profile_source import (
    HUI_LUNG_SAFE_MAX_STEPS_PER_SECOND,
    HuiProfileSourceError,
    persist_hui_profile_source,
)

router = APIRouter(prefix="/hui/profile", tags=["hardware-hui-profile"])


class HuiProfileSourceRequest(BaseModel):
    content: str = Field(min_length=1, max_length=256 * 1024)


@router.put("/source")
async def save_hui_profile_source(
    payload: HuiProfileSourceRequest,
    x_connect_role: str | None = Header(default=None, alias="X-Connect-Role"),
) -> dict[str, Any]:
    """Persist a validated profile; no output is energized and no motion is issued."""
    _require_system_role(x_connect_role)
    try:
        result = persist_hui_profile_source(payload.content)
    except HuiProfileSourceError as exc:
        raise OqlosError(
            code="api_hardware_configuration_invalid",
            status_code=422,
            message=str(exc),
            detail={
                "component": "hardware-hui-profile",
                "stage": "profile.validate",
                "operation_id": "hardware.hui.profile.save",
                "safe_max_steps_per_second": HUI_LUNG_SAFE_MAX_STEPS_PER_SECOND,
            },
        ) from exc
    except OSError as exc:
        raise _configuration_unavailable(
            "hardware.hui.profile.save", stage="profile.persist"
        ) from exc
    return {
        "ok": True,
        "persisted": True,
        "applied": True,
        "applies_on": "next-start",
        "requires_service_restart": False,
        "requires_motion_restart": True,
        "safe_max_steps_per_second": HUI_LUNG_SAFE_MAX_STEPS_PER_SECOND,
        **result,
    }
