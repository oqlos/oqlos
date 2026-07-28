"""Versioned, format-neutral OqlOS hardware configuration.

All supported file formats are codecs for the same :class:`HardwareConfiguration`
model.  Runtime consumers must load this model instead of branching on YAML,
JSON, or OQL themselves.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import tempfile
from typing import Any

import yaml
from pydantic import ValidationError

from oqlos.core.oql_versioning import OQL_VERSION_CURRENT

from .configuration_migration import migrate_legacy_hardware_document
from .configuration_models import (
    HARDWARE_CONFIGURATION_VERSION,
    SUPPORTED_HARDWARE_CONFIGURATION_FORMATS,
    HardwareAlias,
    HardwareConfiguration,
    HardwareConfigurationError,
    HardwareProcess,
    SecretReference,
    validation_issues,
)

__all__ = [
    "HARDWARE_CONFIGURATION_VERSION",
    "SUPPORTED_HARDWARE_CONFIGURATION_FORMATS",
    "HardwareAlias",
    "HardwareConfiguration",
    "HardwareConfigurationError",
    "HardwareProcess",
    "SecretReference",
    "detect_hardware_configuration_format",
    "load_effective_hardware_configuration",
    "load_hardware_configuration",
    "migrate_legacy_hardware_document",
    "normalize_hardware_configuration",
    "parse_hardware_configuration",
    "resolve_effective_hardware_configuration",
    "save_hardware_configuration",
    "semantic_configuration_diff",
    "serialize_hardware_configuration",
]


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
        f"VERSION: {OQL_VERSION_CURRENT}",
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
        issues = validation_issues(exc)
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
