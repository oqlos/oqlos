"""Persistent OqlOS hardware MAP store with JSON/YAML import-export."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from oqlos.api.hardware_mapping_access import MAP_BODY_SECTIONS, merge_mapping_sections
from oqlos.api.hardware_mapping_contract import MappingContractError, validate_mapping_contract
from oqlos.hardware.client.tic249_arg_contract import (
    MOTOR2_RUNTIME_ALIASES,
    canonicalize_motor2_runtime_key,
)
from oqlos.shared.file_ops import env_configured_path

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency failure
    yaml = None


def _default_path() -> Path:
    return env_configured_path(
        ("OQLOS_HARDWARE_MAP_FILE", "HARDWARE_MAP_FILE"),
        Path.home() / "oqlos" / "hardware-map.yaml",
    )


def empty_mapping() -> dict[str, Any]:
    return {
        "meta": {"access": {"model": "hierarchical-system-admin-operator"}},
        "runtimeConfig": {},
        "objectActionMap": {},
        "paramSensorMap": {},
        "actions": {},
        "funcImplementations": {},
        "operatorVariables": {},
    }


def _normalize_motor2_runtime_config(runtime_config: dict[str, Any]) -> dict[str, Any]:
    normalized = {k: v for k, v in runtime_config.items() if k not in MOTOR2_RUNTIME_ALIASES}
    motor2: dict[str, Any] = {}
    for alias in MOTOR2_RUNTIME_ALIASES:
        candidate = runtime_config.get(alias)
        if not isinstance(candidate, dict):
            continue
        for key, value in candidate.items():
            motor2[canonicalize_motor2_runtime_key(key)] = value
    if motor2:
        normalized["motor2"] = motor2
    return normalized


def normalize_mapping(value: Any) -> dict[str, Any]:
    src = value if isinstance(value, dict) else {}
    validate_mapping_contract(src)
    runtime_config = src.get("runtimeConfig") if isinstance(src.get("runtimeConfig"), dict) else {}
    runtime_config = _normalize_motor2_runtime_config(runtime_config)
    mapping = {
        "meta": src.get("meta") if isinstance(src.get("meta"), dict) else {},
        "runtimeConfig": runtime_config,
        "objectActionMap": src.get("objectActionMap") if isinstance(src.get("objectActionMap"), dict) else {},
        "paramSensorMap": src.get("paramSensorMap") if isinstance(src.get("paramSensorMap"), dict) else {},
        "actions": src.get("actions") if isinstance(src.get("actions"), dict) else {},
        "funcImplementations": src.get("funcImplementations")
        if isinstance(src.get("funcImplementations"), dict)
        else {},
        "operatorVariables": src.get("operatorVariables")
        if isinstance(src.get("operatorVariables"), dict)
        else {},
    }
    for section in MAP_BODY_SECTIONS:
        mapping.setdefault(section, {})
    validate_mapping_contract(mapping)
    return mapping


class MappingStore:
    def __init__(self, file_path: str | Path | None = None) -> None:
        self._path = Path(file_path).expanduser() if file_path else _default_path()
        self._mapping = empty_mapping()
        self._load_from_disk()

    @property
    def file_path(self) -> str:
        return str(self._path)

    @property
    def storage_backend(self) -> str:
        return "file"

    def _load_from_disk(self) -> None:
        if not self._path.exists():
            return
        raw = self._path.read_text(encoding="utf-8")
        fmt = "json" if self._path.suffix.lower() == ".json" else "yaml"
        try:
            self._mapping = normalize_mapping(self.parse_text(raw, fmt))
        except (MappingContractError, json.JSONDecodeError, RuntimeError, TypeError, ValueError):
            self._mapping = empty_mapping()

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.suffix.lower() == ".json":
            payload = json.dumps(self._mapping, ensure_ascii=False, indent=2)
        else:
            if yaml is None:
                raise RuntimeError("PyYAML is required to persist YAML mapping file")
            payload = yaml.safe_dump(self._mapping, sort_keys=False, allow_unicode=True)
        self._path.write_text(payload, encoding="utf-8")

    def get(self, *, refresh: bool = True) -> dict[str, Any]:
        if refresh:
            self._load_from_disk()
        return deepcopy(self._mapping)

    def replace(self, mapping: dict[str, Any], *, persist: bool = True) -> dict[str, Any]:
        self._mapping = normalize_mapping(mapping)
        if persist:
            self.save()
        return deepcopy(self._mapping)

    def merge_sections(
        self,
        patch: dict[str, Any],
        *,
        sections: list[str] | tuple[str, ...] | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        current = self.get(refresh=True)
        merged = merge_mapping_sections(current, patch, sections=sections)
        return self.replace(merged, persist=persist)

    def reset(self, *, persist: bool = True) -> dict[str, Any]:
        self._mapping = empty_mapping()
        if persist:
            self.save()
        return self.get(refresh=False)

    @staticmethod
    def parse_text(content: str, fmt: str) -> dict[str, Any]:
        mode = (fmt or "").strip().lower()
        if mode == "json":
            value = json.loads(content or "{}")
        elif mode == "yaml":
            if yaml is None:
                raise RuntimeError("PyYAML is required for YAML mapping import/export")
            value = yaml.safe_load(content) if content.strip() else {}
        else:
            raise ValueError("Unsupported format, expected 'json' or 'yaml'")
        if not isinstance(value, dict):
            raise ValueError("Mapping content must deserialize to an object")
        return normalize_mapping(value)

    def import_text(self, content: str, fmt: str, *, persist: bool = True) -> dict[str, Any]:
        mapping = self.parse_text(content, fmt)
        return self.replace(mapping, persist=persist)

    def export_text(self, fmt: str) -> str:
        mode = (fmt or "").strip().lower()
        if mode == "json":
            return json.dumps(self._mapping, ensure_ascii=False, indent=2)
        if mode == "yaml":
            if yaml is None:
                raise RuntimeError("PyYAML is required for YAML mapping export")
            return yaml.safe_dump(self._mapping, sort_keys=False, allow_unicode=True)
        raise ValueError("Unsupported format, expected 'json' or 'yaml'")


mapping_store = MappingStore()
