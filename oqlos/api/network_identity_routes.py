"""OQL API for Linux node network identity."""

from typing import Any

from fastapi import APIRouter, Header
from pydantic import BaseModel

from oqlos.errors import OqlosError
from oqlos.hardware.network_identity import (
    NETWORK_IDENTITY_VERSION,
    NetworkIdentityConfiguration,
    NetworkIdentityError,
    apply_network_identity,
)

router = APIRouter(prefix="/network-identity", tags=["network-identity"])


class ApplyRequest(BaseModel):
    configuration: NetworkIdentityConfiguration
    dry_run: bool = True
    confirm: bool = False


@router.get("")
async def network_identity_status() -> dict[str, Any]:
    return {"ok": True, "contract": NETWORK_IDENTITY_VERSION}


@router.post("/validate")
async def validate_network_identity(config: NetworkIdentityConfiguration) -> dict[str, Any]:
    return apply_network_identity(config, dry_run=True)


@router.post("/apply")
async def apply_network_identity_route(
    payload: ApplyRequest,
    x_connect_role: str | None = Header(default=None, alias="X-Connect-Role"),
) -> dict[str, Any]:
    if not payload.dry_run:
        if str(x_connect_role or "").lower() not in {"system", "admin", "administrator"}:
            raise OqlosError(code="api_hardware_configuration_write_forbidden", status_code=403)
        if not payload.confirm:
            raise OqlosError(code="api_hardware_configuration_write_forbidden", status_code=403,
                             message="live network identity apply requires confirm=true")
    try:
        return apply_network_identity(payload.configuration, dry_run=payload.dry_run)
    except NetworkIdentityError as exc:
        raise OqlosError(code="api_hardware_configuration_invalid", status_code=422,
                         message=str(exc)) from exc
