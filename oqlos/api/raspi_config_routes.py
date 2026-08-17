"""OQL raspi-config API: validate desired state and apply allowlisted nonint commands."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from oqlos.errors import OqlosError
from oqlos.hardware.raspi_config import (
    RASPI_CONFIG_VERSION,
    SUPPORTED_RASPI_CONFIG_FORMATS,
    RaspiConfigError,
    apply_raspi_config,
    parse_raspi_configuration,
    probe_raspi_config,
    serialize_raspi_configuration,
)

router = APIRouter(prefix="/raspi-config", tags=["raspi-config"])


class RaspiConfigContentRequest(BaseModel):
    content: str = Field(min_length=1)
    format: Literal["oql", "yaml", "json"]


class RaspiConfigApplyRequest(RaspiConfigContentRequest):
    dry_run: bool = True
    confirm: bool = False


def _invalid(operation_id: str, exc: RaspiConfigError) -> OqlosError:
    return OqlosError(
        code="api_hardware_configuration_invalid",
        status_code=422,
        detail={
            "architecture": "SOA",
            "layer": "oqlos",
            "component": "raspi-config",
            "stage": "document.validate",
            "problem_source": "request",
            "operation_id": operation_id,
            "issues": exc.issues,
        },
        message=str(exc),
    )


def _require_system_role(role: str | None) -> None:
    if str(role or "").strip().lower() not in {"system", "administrator", "admin"}:
        raise OqlosError(
            code="api_hardware_configuration_write_forbidden",
            status_code=403,
            detail={
                "architecture": "SOA",
                "layer": "oqlos",
                "component": "raspi-config",
                "stage": "role.authorize",
                "problem_source": "request",
                "operation_id": "raspi.config.apply",
            },
        )


@router.get("")
async def get_raspi_config() -> dict[str, Any]:
    return {
        "ok": True,
        "contract": RASPI_CONFIG_VERSION,
        "formats": list(SUPPORTED_RASPI_CONFIG_FORMATS),
        "status": probe_raspi_config(),
    }


@router.post("/validate")
async def validate_raspi_config(payload: RaspiConfigContentRequest) -> dict[str, Any]:
    try:
        config = parse_raspi_configuration(payload.content, payload.format)
    except RaspiConfigError as exc:
        raise _invalid("raspi.config.validate", exc) from exc
    return {
        "ok": True,
        "contract": RASPI_CONFIG_VERSION,
        "configuration": config.canonical_dict(),
        "oql": serialize_raspi_configuration(config, "oql"),
    }


@router.post("/apply")
async def apply_raspi_config_source(
    payload: RaspiConfigApplyRequest,
    x_connect_role: str | None = Header(default=None, alias="X-Connect-Role"),
) -> dict[str, Any]:
    if not payload.dry_run:
        _require_system_role(x_connect_role)
        if not payload.confirm:
            raise OqlosError(
                code="api_hardware_configuration_write_forbidden",
                status_code=403,
                detail={
                    "architecture": "SOA",
                    "layer": "oqlos",
                    "component": "raspi-config",
                    "stage": "confirm",
                    "problem_source": "request",
                    "operation_id": "raspi.config.apply",
                },
                message="live raspi-config apply requires confirm=true",
            )
    try:
        config = parse_raspi_configuration(payload.content, payload.format)
        return apply_raspi_config(config, dry_run=payload.dry_run)
    except RaspiConfigError as exc:
        if "policy" in str(exc) or "not installed" in str(exc) or "not available" in str(exc):
            raise OqlosError(
                code="api_hardware_configuration_write_forbidden",
                status_code=403,
                detail={
                    "architecture": "SOA",
                    "layer": "oqlos",
                    "component": "raspi-config",
                    "stage": "apply",
                    "problem_source": "policy",
                    "operation_id": "raspi.config.apply",
                },
                message=str(exc),
            ) from exc
        raise _invalid("raspi.config.apply", exc) from exc
