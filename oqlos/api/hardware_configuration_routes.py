"""Format-neutral hardware configuration API.

These endpoints only validate and persist configuration.  They never execute
hardware commands or energize outputs; activating a new file requires the
normal, separately controlled service restart workflow.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Literal

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, Field

from oqlos.errors import OqlosError
from oqlos.hardware.config_paths import resolve_oqlos_config_path
from oqlos.hardware.configuration import (
    HARDWARE_CONFIGURATION_VERSION,
    SUPPORTED_HARDWARE_CONFIGURATION_FORMATS,
    HardwareConfiguration,
    HardwareConfigurationError,
    detect_hardware_configuration_format,
    load_hardware_configuration,
    parse_hardware_configuration,
    resolve_effective_hardware_configuration,
    save_hardware_configuration,
    semantic_configuration_diff,
    serialize_hardware_configuration,
)

router = APIRouter(prefix="/configuration", tags=["hardware-configuration"])


class ConfigurationContentRequest(BaseModel):
    content: str = Field(min_length=1)
    format: Literal["oql", "yaml", "json"]


class ConfigurationConvertRequest(ConfigurationContentRequest):
    target_format: Literal["oql", "yaml", "json"]


class ConfigurationSaveRequest(ConfigurationContentRequest):
    file_name: str | None = None


def _configuration_unavailable(operation_id: str, *, stage: str) -> OqlosError:
    return OqlosError(
        code="config_unavailable",
        status_code=503,
        detail={
            "architecture": "SOA",
            "layer": "oqlos",
            "component": "hardware-configuration",
            "stage": stage,
            "problem_source": "configuration",
            "operation_id": operation_id,
        },
    )


def _configuration_invalid(
    operation_id: str,
    *,
    stage: str,
    reason: str,
    exc: HardwareConfigurationError | None = None,
) -> OqlosError:
    detail: dict[str, Any] = {
        "architecture": "SOA",
        "layer": "oqlos",
        "component": "hardware-configuration",
        "stage": stage,
        "problem_source": "request",
        "operation_id": operation_id,
        "reason": reason,
    }
    if exc is not None:
        if exc.format in SUPPORTED_HARDWARE_CONFIGURATION_FORMATS:
            detail["format"] = exc.format
        if exc.issues:
            detail["issue_count"] = len(exc.issues)
    return OqlosError(
        code="api_hardware_configuration_invalid",
        status_code=422,
        detail=detail,
    )


def _configuration_error(
    exc: HardwareConfigurationError,
    *,
    operation_id: str,
    stage: str,
    configured_source: bool = False,
) -> OqlosError:
    if configured_source or isinstance(exc.__cause__, OSError):
        return _configuration_unavailable(operation_id, stage=stage)
    return _configuration_invalid(
        operation_id,
        stage=stage,
        reason="configuration_invalid",
        exc=exc,
    )


def _require_system_role(role: str | None) -> None:
    if str(role or "").strip().lower() not in {"system", "administrator", "admin"}:
        raise OqlosError(
            code="api_hardware_configuration_write_forbidden",
            status_code=403,
            detail={
                "architecture": "SOA",
                "layer": "oqlos",
                "component": "hardware-configuration",
                "stage": "role.authorize",
                "problem_source": "request",
                "operation_id": "hardware.configuration.save",
            },
        )


def _configured_path(operation_id: str) -> Path:
    try:
        return resolve_oqlos_config_path()
    except FileNotFoundError as exc:
        raise _configuration_unavailable(operation_id, stage="config.resolve") from exc


def _safe_target(file_name: str | None) -> Path:
    name = None
    if file_name:
        name = Path(file_name).name
        if name != file_name or not re.fullmatch(
            r"oqlos(?:-[A-Za-z0-9_.-]+)?\.(?:oql|ya?ml|json)", name
        ):
            raise _configuration_invalid(
                "hardware.configuration.save",
                stage="target.validate",
                reason="file_name_invalid",
            )
    current = _configured_path("hardware.configuration.save")
    if name is None:
        return current
    return current.parent / name


def _configuration_payload(config: HardwareConfiguration, path: Path) -> dict[str, Any]:
    effective, overrides = resolve_effective_hardware_configuration(config)
    return {
        "ok": True,
        "contract": HARDWARE_CONFIGURATION_VERSION,
        "format": detect_hardware_configuration_format(path),
        "path": str(path),
        "configured": config.canonical_dict(),
        "effective": effective.canonical_dict(),
        "overrides": overrides,
        "diff": semantic_configuration_diff(config, effective),
        "requires_restart": bool(overrides),
    }


@router.get("")
async def get_hardware_configuration() -> dict[str, Any]:
    path = _configured_path("hardware.configuration.get")
    try:
        return _configuration_payload(load_hardware_configuration(path), path)
    except HardwareConfigurationError as exc:
        raise _configuration_error(
            exc,
            operation_id="hardware.configuration.get",
            stage="config.load",
            configured_source=True,
        ) from exc


@router.get("/schema")
async def get_hardware_configuration_schema() -> dict[str, Any]:
    return {
        "ok": True,
        "contract": HARDWARE_CONFIGURATION_VERSION,
        "formats": list(SUPPORTED_HARDWARE_CONFIGURATION_FORMATS),
        "schema": HardwareConfiguration.model_json_schema(by_alias=True),
    }


@router.get("/files")
async def list_hardware_configuration_files() -> dict[str, Any]:
    current = _configured_path("hardware.configuration.files.list")
    files: list[dict[str, Any]] = []
    for candidate in sorted(current.parent.glob("oqlos*")):
        if not candidate.is_file() or candidate.suffix.lower() not in {".oql", ".yaml", ".yml", ".json"}:
            continue
        try:
            fmt = detect_hardware_configuration_format(candidate)
            load_hardware_configuration(candidate)
            valid = True
            error = None
        except HardwareConfigurationError:
            fmt = candidate.suffix.lower().lstrip(".").replace("yml", "yaml")
            valid = False
            error = "Invalid hardware configuration"
        files.append({
            "name": candidate.name,
            "path": str(candidate),
            "format": fmt,
            "active": candidate.resolve() == current.resolve(),
            "valid": valid,
            "error": error,
            "error_code": None if valid else "C2004-DATA-0002",
            "issue_code": None if valid else "api_hardware_configuration_invalid",
        })
    return {"ok": True, "count": len(files), "files": files}


@router.get("/source")
async def get_hardware_configuration_source(
    format: Literal["oql", "yaml", "json"] | None = Query(default=None),
) -> dict[str, Any]:
    path = _configured_path("hardware.configuration.source.get")
    try:
        config = load_hardware_configuration(path)
        output_format = format or detect_hardware_configuration_format(path)
        return {
            "ok": True,
            "name": path.name,
            "active_format": detect_hardware_configuration_format(path),
            "format": output_format,
            "content": serialize_hardware_configuration(config, output_format),
            "contract": HARDWARE_CONFIGURATION_VERSION,
        }
    except HardwareConfigurationError as exc:
        raise _configuration_error(
            exc,
            operation_id="hardware.configuration.source.get",
            stage="config.load",
            configured_source=True,
        ) from exc


@router.post("/validate")
async def validate_hardware_configuration(payload: ConfigurationContentRequest) -> dict[str, Any]:
    try:
        config = parse_hardware_configuration(payload.content, payload.format)
    except HardwareConfigurationError as exc:
        raise _configuration_error(
            exc,
            operation_id="hardware.configuration.validate",
            stage="config.validate",
        ) from exc
    return {"ok": True, "contract": config.schema_version, "configuration": config.canonical_dict()}


@router.post("/convert")
async def convert_hardware_configuration(payload: ConfigurationConvertRequest) -> dict[str, Any]:
    try:
        config = parse_hardware_configuration(payload.content, payload.format)
        content = serialize_hardware_configuration(config, payload.target_format)
    except HardwareConfigurationError as exc:
        raise _configuration_error(
            exc,
            operation_id="hardware.configuration.convert",
            stage="config.convert",
        ) from exc
    return {
        "ok": True,
        "contract": config.schema_version,
        "source_format": payload.format,
        "format": payload.target_format,
        "content": content,
    }


@router.put("/source")
async def save_hardware_configuration_source(
    payload: ConfigurationSaveRequest,
    x_connect_role: str | None = Header(default=None, alias="X-Connect-Role"),
) -> dict[str, Any]:
    _require_system_role(x_connect_role)
    target = _safe_target(payload.file_name)
    target_format = detect_hardware_configuration_format(target)
    if target_format != payload.format:
        raise _configuration_invalid(
            "hardware.configuration.save",
            stage="target.validate",
            reason="format_mismatch",
        )
    try:
        config = parse_hardware_configuration(payload.content, payload.format, source=target.name)
        save_hardware_configuration(target, config, format=payload.format)
    except HardwareConfigurationError as exc:
        raise _configuration_error(
            exc,
            operation_id="hardware.configuration.save",
            stage="config.validate",
        ) from exc
    except OSError as exc:
        raise _configuration_unavailable(
            "hardware.configuration.save",
            stage="config.persist",
        ) from exc
    active = target.resolve() == _configured_path("hardware.configuration.save").resolve()
    return {
        "ok": True,
        "name": target.name,
        "path": str(target),
        "format": payload.format,
        "contract": config.schema_version,
        "persisted": True,
        "applied": False,
        "active": active,
        "activation_requires_config_path_change": not active,
        "requires_restart": True,
    }
