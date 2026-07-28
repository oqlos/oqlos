"""Explicit migration of legacy hardware maps to hardware-configuration-v1."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .configuration_models import HARDWARE_CONFIGURATION_VERSION, HardwareConfigurationError

_CANONICAL_FIELDS = {
    "metadata",
    "devices",
    "plugins",
    "aliases",
    "sensors",
    "processes",
    "actions",
    "functions",
    "profiles",
    "runtime",
    "variables",
    "policies",
    "secretRefs",
    "secret_refs",
}
_LEGACY_FIELDS = {
    "runtimeConfig",
    "objectActionMap",
    "paramSensorMap",
    "funcImplementations",
    "operatorVariables",
    "meta",
}
_FIELD_SOURCES: dict[str, tuple[str, ...]] = {
    "metadata": ("metadata", "meta"),
    "devices": ("devices",),
    "plugins": ("plugins",),
    "aliases": ("aliases",),
    "sensors": ("sensors",),
    "processes": ("processes",),
    "actions": ("actions",),
    "functions": ("functions", "funcImplementations"),
    "profiles": ("profiles",),
    "runtime": ("runtime", "runtimeConfig"),
    "variables": ("variables", "operatorVariables"),
    "policies": ("policies",),
    "secretRefs": ("secretRefs", "secret_refs"),
}


def _first_mapping(value: dict[str, Any], names: tuple[str, ...]) -> dict[str, Any]:
    for name in names:
        candidate = value.get(name)
        if candidate:
            return deepcopy(candidate)
    return {}


def _reject_unknown_fields(value: dict[str, Any]) -> None:
    unknown = set(value) - _CANONICAL_FIELDS - _LEGACY_FIELDS
    if unknown:
        raise HardwareConfigurationError(
            "unknown top-level fields in legacy configuration",
            issues=[{"field": key, "message": "unknown field"} for key in sorted(unknown)],
        )


def _merge_legacy_bindings(migrated: dict[str, Any], value: dict[str, Any]) -> None:
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


def migrate_legacy_hardware_document(value: Any) -> dict[str, Any]:
    """Convert legacy plugin YAML or hardware-map JSON/YAML into v1."""
    if not isinstance(value, dict):
        raise HardwareConfigurationError("configuration root must be an object")
    if value.get("schemaVersion") or value.get("schema_version"):
        return dict(value)

    _reject_unknown_fields(value)
    migrated = {
        "schemaVersion": HARDWARE_CONFIGURATION_VERSION,
        **{
            field: _first_mapping(value, sources)
            for field, sources in _FIELD_SOURCES.items()
        },
    }
    _merge_legacy_bindings(migrated, value)
    migrated["metadata"].setdefault("migration", {})
    migrated["metadata"]["migration"].update({
        "source": "legacy-hardware-configuration",
        "contract": HARDWARE_CONFIGURATION_VERSION,
    })
    return migrated
