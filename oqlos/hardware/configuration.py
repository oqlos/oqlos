"""Versioned, format-neutral OqlOS hardware configuration.

All supported file formats are codecs for the same :class:`HardwareConfiguration`
model.  Runtime consumers must load this model instead of branching on YAML,
JSON, or OQL themselves.
"""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import re
import shlex
import tempfile
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from oqlos.hardware.plugins.base import PluginConfig

HARDWARE_CONFIGURATION_VERSION = "hardware-configuration-v1"
SUPPORTED_HARDWARE_CONFIGURATION_FORMATS = ("oql", "yaml", "json")


class _HardwareYamlLoader(yaml.SafeLoader):
    """YAML loader with YAML-1.2-style booleans (only true/false).

    PyYAML's YAML 1.1 resolver turns keys such as ``on`` and ``off`` into
    booleans, which corrupts action maps during format conversion.
    """


for first_char, resolvers in list(_HardwareYamlLoader.yaml_implicit_resolvers.items()):
    _HardwareYamlLoader.yaml_implicit_resolvers[first_char] = [
        item for item in resolvers if item[0] != "tag:yaml.org,2002:bool"
    ]
_HardwareYamlLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|false|True|False|TRUE|FALSE)$"),
    list("tTfF"),
)


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


class HardwareConfiguration(BaseModel):
    """Canonical portable configuration shared by OQL, YAML, and JSON.

    The top-level vocabulary is strict.  Extension-shaped hardware payloads
    live inside named dictionaries, so adding a driver does not require a new
    serialization path while misspelled top-level sections are still rejected.
    """

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
        secret_key = re.compile(r"(?:^|_)(?:password|passwd|token|api_key|secret)(?:$|_)", re.I)

        def walk(value: Any, path: tuple[str, ...]) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    child_path = (*path, str(key))
                    if secret_key.search(str(key)) and child not in (None, "", {}):
                        raise ValueError(
                            f"inline secret at {'.'.join(child_path)}; use secretRefs instead"
                        )
                    walk(child, child_path)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    walk(child, (*path, str(index)))

        portable = self.model_dump(by_alias=True, exclude={"secret_refs"})
        walk(portable, ())
        return self

    @model_validator(mode="after")
    def _validate_runtime_contracts(self) -> "HardwareConfiguration":
        motor2 = self.runtime.get("motor2")
        if motor2 is None:
            return self
        if not isinstance(motor2, dict):
            raise ValueError("runtime.motor2 must be an object")

        def positive_integer(field: str) -> None:
            value = motor2.get(field)
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 1
            ):
                raise ValueError(f"runtime.motor2.{field} must be an integer >= 1")

        for field in ("strokeSteps", "maxStepsPerSecond", "defaultSpeedStepsPerSecond"):
            positive_integer(field)
        maximum = motor2.get("maxStepsPerSecond")
        default = motor2.get("defaultSpeedStepsPerSecond")
        if isinstance(maximum, int) and isinstance(default, int) and default > maximum:
            raise ValueError(
                "runtime.motor2.defaultSpeedStepsPerSecond must be <= maxStepsPerSecond"
            )
        peripheral_id = motor2.get("peripheralId")
        if peripheral_id is not None and (
            not isinstance(peripheral_id, str) or not peripheral_id.strip()
        ):
            raise ValueError("runtime.motor2.peripheralId must be a non-empty string")
        cycle_volume = motor2.get("cycleVolumeLiters")
        if cycle_volume is not None and (
            isinstance(cycle_volume, bool)
            or not isinstance(cycle_volume, (int, float))
            or cycle_volume <= 0
        ):
            raise ValueError("runtime.motor2.cycleVolumeLiters must be a number > 0")
        acceleration = motor2.get("accelerationPercentPerSecond")
        if acceleration is not None and (
            isinstance(acceleration, bool)
            or not isinstance(acceleration, (int, float))
            or not 0 < acceleration <= 100
        ):
            raise ValueError(
                "runtime.motor2.accelerationPercentPerSecond must be in range (0, 100]"
            )
        if motor2.get("startDirection") not in {None, "left", "right"}:
            raise ValueError("runtime.motor2.startDirection must be left or right")
        if motor2.get("limitMode") not in {None, "stop_on_limit", "reverse_on_limit"}:
            raise ValueError(
                "runtime.motor2.limitMode must be stop_on_limit or reverse_on_limit"
            )
        return self

    def canonical_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


def _validation_issues(exc: ValidationError) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for error in exc.errors(include_url=False):
        issues.append({
            "field": ".".join(str(part) for part in error.get("loc", ())),
            "message": error.get("msg", "invalid value"),
            "type": error.get("type", "validation_error"),
        })
    return issues


def migrate_legacy_hardware_document(value: Any) -> dict[str, Any]:
    """Convert legacy plugin YAML or hardware-map JSON/YAML into v1.

    This is deliberately explicit and is used by the offline migrator and by
    the runtime compatibility boundary.  No runtime consumer reads the legacy
    sections after this function returns.
    """
    if not isinstance(value, dict):
        raise HardwareConfigurationError("configuration root must be an object")
    if value.get("schemaVersion") or value.get("schema_version"):
        return dict(value)

    known_new = {
        "metadata", "devices", "plugins", "aliases", "sensors", "processes",
        "actions", "functions", "profiles", "runtime", "variables", "policies",
        "secretRefs", "secret_refs",
    }
    legacy_map = {
        "runtimeConfig", "objectActionMap", "paramSensorMap", "actions",
        "funcImplementations", "operatorVariables", "meta",
    }
    unknown = set(value) - known_new - legacy_map
    if unknown:
        raise HardwareConfigurationError(
            "unknown top-level fields in legacy configuration",
            issues=[{"field": key, "message": "unknown field"} for key in sorted(unknown)],
        )

    migrated: dict[str, Any] = {
        "schemaVersion": HARDWARE_CONFIGURATION_VERSION,
        "metadata": deepcopy(value.get("metadata") or value.get("meta") or {}),
        "devices": deepcopy(value.get("devices") or {}),
        "plugins": deepcopy(value.get("plugins") or {}),
        "aliases": deepcopy(value.get("aliases") or {}),
        "sensors": deepcopy(value.get("sensors") or {}),
        "processes": deepcopy(value.get("processes") or {}),
        "actions": deepcopy(value.get("actions") or {}),
        "functions": deepcopy(value.get("functions") or value.get("funcImplementations") or {}),
        "profiles": deepcopy(value.get("profiles") or {}),
        "runtime": deepcopy(value.get("runtime") or value.get("runtimeConfig") or {}),
        "variables": deepcopy(value.get("variables") or value.get("operatorVariables") or {}),
        "policies": deepcopy(value.get("policies") or {}),
        "secretRefs": deepcopy(value.get("secretRefs") or value.get("secret_refs") or {}),
    }
    if value.get("objectActionMap"):
        migrated["actions"] = {
            **migrated["actions"],
            "objects": deepcopy(value["objectActionMap"]),
        }
    if value.get("paramSensorMap"):
        migrated["sensors"] = {
            **migrated["sensors"],
            "bindings": deepcopy(value["paramSensorMap"]),
        }
    migrated["metadata"].setdefault("migration", {})
    migrated["metadata"]["migration"].update({
        "source": "legacy-hardware-configuration",
        "contract": HARDWARE_CONFIGURATION_VERSION,
    })
    return migrated


_OQL_KEY_PREFIX = "hardware.configuration."


def _parse_oql(text: str, source: str | None) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped.upper().startswith("SET "):
            continue
        try:
            tokens = shlex.split(stripped, comments=True, posix=True)
        except ValueError as exc:
            raise HardwareConfigurationError(
                f"invalid OQL SET at line {line_number}: {exc}", format="oql", source=source
            ) from exc
        if len(tokens) != 3 or tokens[0].upper() != "SET" or not tokens[1].startswith(_OQL_KEY_PREFIX):
            continue
        field = tokens[1][len(_OQL_KEY_PREFIX):]
        try:
            document[field] = json.loads(tokens[2])
        except json.JSONDecodeError as exc:
            raise HardwareConfigurationError(
                f"invalid JSON value for {field} at line {line_number}: {exc.msg}",
                format="oql",
                source=source,
            ) from exc
    if not document:
        raise HardwareConfigurationError(
            f"no {_OQL_KEY_PREFIX}* SET declarations found", format="oql", source=source
        )
    return document


def _dump_oql(config: HardwareConfiguration) -> str:
    lines = [
        "VERSION: 5",
        "SCENARIO: OqlOS hardware configuration",
        "CATEGORY: hardware-configuration",
        "DESCRIPTION: Versioned portable hardware configuration; generated deterministically.",
        "",
        "CONFIG:",
        "  NAME 'OqlOS hardware configuration'",
    ]
    for field, value in config.canonical_dict().items():
        compact = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        quoted = json.dumps(compact, ensure_ascii=False)
        lines.append(f"  SET '{_OQL_KEY_PREFIX}{field}' {quoted}")
    return "\n".join(lines) + "\n"


def normalize_hardware_configuration(
    value: Any,
    *,
    format: str | None = None,
    source: str | None = None,
    allow_legacy: bool = False,
) -> HardwareConfiguration:
    try:
        candidate = migrate_legacy_hardware_document(value) if allow_legacy else value
        return HardwareConfiguration.model_validate(candidate)
    except HardwareConfigurationError:
        raise
    except ValidationError as exc:
        issues = _validation_issues(exc)
        detail = issues[0]["message"] if issues else "invalid value"
        raise HardwareConfigurationError(
            f"hardware configuration validation failed: {detail}",
            format=format,
            source=source,
            issues=issues,
        ) from exc


def detect_hardware_configuration_format(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix == ".oql":
        return "oql"
    raise HardwareConfigurationError(
        "unsupported configuration extension; expected .oql, .yaml/.yml, or .json",
        source=str(path),
    )


def parse_hardware_configuration(
    content: str,
    format: str,
    *,
    source: str | None = None,
    allow_legacy: bool = False,
) -> HardwareConfiguration:
    mode = str(format or "").strip().lower()
    try:
        if mode == "json":
            value = json.loads(content)
        elif mode == "yaml":
            value = yaml.load(content, Loader=_HardwareYamlLoader)
        elif mode == "oql":
            value = _parse_oql(content, source)
        else:
            raise HardwareConfigurationError(
                "unsupported format; expected oql, yaml, or json", format=mode, source=source
            )
    except HardwareConfigurationError:
        raise
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise HardwareConfigurationError(str(exc), format=mode, source=source) from exc
    return normalize_hardware_configuration(
        value,
        format=mode,
        source=source,
        allow_legacy=allow_legacy,
    )


def serialize_hardware_configuration(config: HardwareConfiguration, format: str) -> str:
    mode = str(format or "").strip().lower()
    data = config.canonical_dict()
    if mode == "json":
        return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if mode == "yaml":
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=True)
    if mode == "oql":
        return _dump_oql(config)
    raise HardwareConfigurationError("unsupported format; expected oql, yaml, or json", format=mode)


def load_hardware_configuration(
    path: str | Path,
    *,
    allow_legacy: bool = True,
) -> HardwareConfiguration:
    resolved = Path(path).expanduser()
    try:
        content = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        raise HardwareConfigurationError(str(exc), source=str(resolved)) from exc
    return parse_hardware_configuration(
        content,
        detect_hardware_configuration_format(resolved),
        source=str(resolved),
        allow_legacy=allow_legacy,
    )


def save_hardware_configuration(
    path: str | Path,
    config: HardwareConfiguration,
    *,
    format: str | None = None,
) -> Path:
    target = Path(path).expanduser()
    mode = format or detect_hardware_configuration_format(target)
    payload = serialize_hardware_configuration(config, mode)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target


_ENV_OVERRIDES: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    ("motor-dri0050", "base_url", ("OQLOS_MOTOR_URL", "MOTOR_URL"), "text"),
    ("motor-tic249", "base_url", ("OQLOS_LUNG_MOTOR_URL", "LUNG_MOTOR_URL"), "text"),
    ("piadc", "base_url", ("OQLOS_PIADC_URL", "PIADC_URL"), "text"),
    ("modbus-io", "serial_port", ("OQLOS_MODBUS_SERIAL_PORT", "MODBUS_SERIAL_PORT"), "text"),
    ("modbus-io", "baudrate", ("OQLOS_MODBUS_BAUD", "MODBUS_BAUD"), "int"),
    ("modbus-io", "parity", ("OQLOS_MODBUS_PARITY", "MODBUS_PARITY"), "text"),
    ("modbus-io", "device_id", ("OQLOS_MODBUS_DEVICE_ID", "MODBUS_DEVICE_ID"), "int"),
    ("modbus-adc", "serial_port", ("OQLOS_MODBUS_ADC_SERIAL_PORT", "MODBUS_ADC_SERIAL_PORT"), "text"),
    ("modbus-adc", "baudrate", ("OQLOS_MODBUS_ADC_BAUD", "MODBUS_ADC_BAUD"), "int"),
    ("modbus-adc", "parity", ("OQLOS_MODBUS_ADC_PARITY", "MODBUS_ADC_PARITY"), "text"),
    ("modbus-adc", "device_id", ("OQLOS_MODBUS_ADC_DEVICE_ID", "MODBUS_ADC_DEVICE_ID"), "int"),
)


def resolve_effective_hardware_configuration(
    config: HardwareConfiguration,
    environ: dict[str, str] | None = None,
) -> tuple[HardwareConfiguration, list[dict[str, Any]]]:
    """Apply documented deployment overrides and return an auditable trace."""
    env = os.environ if environ is None else environ
    effective = config.model_copy(deep=True)
    overrides: list[dict[str, Any]] = []
    for plugin_id, parameter, names, kind in _ENV_OVERRIDES:
        plugin = effective.plugins.get(plugin_id)
        if plugin is None:
            continue
        env_name = next((name for name in names if str(env.get(name, "")).strip()), None)
        if env_name is None:
            continue
        raw = str(env[env_name]).strip()
        try:
            value: Any = int(raw) if kind == "int" else raw.rstrip("/") if parameter == "base_url" else raw
        except ValueError as exc:
            raise HardwareConfigurationError(
                f"invalid environment override {env_name}={raw!r}",
                source="environment",
                issues=[{"field": env_name, "message": str(exc)}],
            ) from exc
        previous = plugin.connection_params.get(parameter)
        plugin.connection_params[parameter] = value
        overrides.append({
            "path": f"plugins.{plugin_id}.connection_params.{parameter}",
            "source": env_name,
            "configured": previous,
            "effective": value,
        })
    return effective, overrides


def semantic_configuration_diff(
    configured: HardwareConfiguration,
    effective: HardwareConfiguration,
) -> list[dict[str, Any]]:
    """Return leaf-level configured/effective differences."""
    differences: list[dict[str, Any]] = []

    def walk(left: Any, right: Any, path: tuple[str, ...]) -> None:
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left) | set(right)):
                walk(left.get(key), right.get(key), (*path, str(key)))
            return
        if left != right:
            differences.append({"path": ".".join(path), "configured": left, "effective": right})

    walk(configured.canonical_dict(), effective.canonical_dict(), ())
    return differences


def load_effective_hardware_configuration(
    path: str | Path | None = None,
    environ: dict[str, str] | None = None,
) -> tuple[HardwareConfiguration, list[dict[str, Any]]]:
    """Load the selected file and apply the single documented override layer."""
    if path is None:
        from oqlos.hardware.config_paths import resolve_oqlos_config_path

        path = resolve_oqlos_config_path()
    return resolve_effective_hardware_configuration(
        load_hardware_configuration(path, allow_legacy=True),
        environ,
    )
