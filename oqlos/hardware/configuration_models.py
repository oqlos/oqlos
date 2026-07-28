"""Canonical models and validation rules for hardware-configuration-v1."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from oqlos.hardware.plugins.base import PluginConfig

HARDWARE_CONFIGURATION_VERSION = "hardware-configuration-v1"
SUPPORTED_HARDWARE_CONFIGURATION_FORMATS = ("oql", "yaml", "json")


class HardwareConfigurationError(ValueError):
    """A configuration error with source/format context suitable for an API."""

    def __init__(
        self,
        message: str,
        *,
        format: str | None = None,
        source: str | None = None,
        issues: list[dict[str, Any]] | None = None,
    ) -> None:
        self.format = format
        self.source = source
        self.issues = issues or []
        context = ", ".join(part for part in (format, source) if part)
        super().__init__(f"{message}{f' ({context})' if context else ''}")


class SecretReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["env", "file", "systemd", "secret-store"] = "env"
    key: str = Field(min_length=1)
    optional: bool = False


class HardwareAlias(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plugin: str = Field(min_length=1)
    target: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    unit: str | None = None
    conversion: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HardwareProcess(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uri: str = Field(min_length=1)
    mode: Literal["execute", "query", "read", "write"] = "execute"
    outputs: dict[str, str] = Field(default_factory=dict)
    poll_interval_ms: int | None = Field(default=None, ge=50)
    emit: str | None = None
    timeout_ms: int | None = Field(default=None, ge=1)
    retry_count: int = Field(default=0, ge=0)


_SECRET_KEY = re.compile(r"(?:^|_)(?:password|passwd|token|api_key|secret)(?:$|_)", re.I)


def _reject_inline_secrets(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = (*path, str(key))
            if _SECRET_KEY.search(str(key)) and child not in (None, "", {}):
                raise ValueError(f"inline secret at {'.'.join(child_path)}; use secretRefs instead")
            _reject_inline_secrets(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_inline_secrets(child, (*path, str(index)))


def _optional_positive_integer(motor2: dict[str, Any], field: str) -> int | None:
    value = motor2.get(field)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"runtime.motor2.{field} must be an integer >= 1")
    return value


def _validate_motor2_speed(motor2: dict[str, Any]) -> None:
    _optional_positive_integer(motor2, "strokeSteps")
    maximum = _optional_positive_integer(motor2, "maxStepsPerSecond")
    default = _optional_positive_integer(motor2, "defaultSpeedStepsPerSecond")
    if maximum is not None and default is not None and default > maximum:
        raise ValueError("runtime.motor2.defaultSpeedStepsPerSecond must be <= maxStepsPerSecond")


def _validate_motor2_identity(motor2: dict[str, Any]) -> None:
    peripheral_id = motor2.get("peripheralId")
    if peripheral_id is not None and (
        not isinstance(peripheral_id, str) or not peripheral_id.strip()
    ):
        raise ValueError("runtime.motor2.peripheralId must be a non-empty string")


def _validate_positive_number(motor2: dict[str, Any], field: str) -> None:
    value = motor2.get(field)
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"runtime.motor2.{field} must be a number > 0")


def _validate_motor2_acceleration(motor2: dict[str, Any]) -> None:
    value = motor2.get("accelerationPercentPerSecond")
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 100:
        raise ValueError("runtime.motor2.accelerationPercentPerSecond must be in range (0, 100]")


def _validate_motor2_choices(motor2: dict[str, Any]) -> None:
    if motor2.get("startDirection") not in {None, "left", "right"}:
        raise ValueError("runtime.motor2.startDirection must be left or right")
    if motor2.get("limitMode") not in {None, "stop_on_limit", "reverse_on_limit"}:
        raise ValueError("runtime.motor2.limitMode must be stop_on_limit or reverse_on_limit")
    if motor2.get("idleState") not in {None, "deenergized", "holding"}:
        raise ValueError("runtime.motor2.idleState must be deenergized or holding")
    for field in ("deenergizeOnStop", "deenergizeOnStartup"):
        if motor2.get(field) is not None and not isinstance(motor2[field], bool):
            raise ValueError(f"runtime.motor2.{field} must be a boolean")


def _validate_motor2_runtime(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError("runtime.motor2 must be an object")
    _validate_motor2_speed(value)
    _validate_motor2_identity(value)
    _validate_positive_number(value, "cycleVolumeLiters")
    _validate_motor2_acceleration(value)
    _validate_motor2_choices(value)


class HardwareConfiguration(BaseModel):
    """Canonical portable configuration shared by OQL, YAML, and JSON."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal[HARDWARE_CONFIGURATION_VERSION] = Field(
        default=HARDWARE_CONFIGURATION_VERSION,
        alias="schemaVersion",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
    devices: dict[str, dict[str, Any]] = Field(default_factory=dict)
    plugins: dict[str, PluginConfig] = Field(default_factory=dict)
    aliases: dict[str, HardwareAlias] = Field(default_factory=dict)
    sensors: dict[str, dict[str, Any]] = Field(default_factory=dict)
    processes: dict[str, HardwareProcess] = Field(default_factory=dict)
    actions: dict[str, Any] = Field(default_factory=dict)
    functions: dict[str, Any] = Field(default_factory=dict)
    profiles: dict[str, Any] = Field(default_factory=dict)
    runtime: dict[str, Any] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    policies: dict[str, Any] = Field(default_factory=dict)
    secret_refs: dict[str, SecretReference] = Field(default_factory=dict, alias="secretRefs")

    @field_validator("plugins", mode="before")
    @classmethod
    def _inject_plugin_ids(cls, value: Any) -> Any:
        if value is None:
            return {}
        if not isinstance(value, dict):
            return value
        return {
            str(plugin_id): ({"plugin_id": str(plugin_id), **data} if isinstance(data, dict) else data)
            for plugin_id, data in value.items()
        }

    @model_validator(mode="after")
    def _reject_inline_secrets(self) -> "HardwareConfiguration":
        portable = self.model_dump(by_alias=True, exclude={"secret_refs"})
        _reject_inline_secrets(portable)
        return self

    @model_validator(mode="after")
    def _validate_runtime_contracts(self) -> "HardwareConfiguration":
        _validate_motor2_runtime(self.runtime.get("motor2"))
        return self

    def canonical_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


def validation_issues(exc: ValidationError) -> list[dict[str, Any]]:
    return [
        {
            "field": ".".join(str(part) for part in error.get("loc", ())),
            "message": error.get("msg", "invalid value"),
            "type": error.get("type", "validation_error"),
        }
        for error in exc.errors(include_url=False)
    ]
