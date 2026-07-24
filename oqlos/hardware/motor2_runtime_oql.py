"""Load runtimeConfig.motor2 from OQL SET keys (MAP → OQL migration slice 2d).

Source file (default): ``layers/hardware/motor2-runtime.oql`` under
``OQLOS_SCENARIOS_DIR`` (or paths listed in ``OQLOS_MOTOR2_RUNTIME_OQL``).

Keys (camelCase or snake_case field after ``runtime.motor2.``):
  peripheralId, strokeSteps, cycleVolumeLiters, maxStepsPerSecond,
  defaultSpeedStepsPerSecond, speedUnit, accelerationPercentPerSecond,
  accelerationUnit, limitMode, startDirection

Merge order for consumers of mapping_store.get():
  MAP runtimeConfig.motor2  <  OQL motor2-runtime.oql  (OQL wins per key)
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from oqlos.hardware.client.tic249_arg_contract import canonicalize_motor2_runtime_key

_SET_RE = re.compile(
    r"""^\s*SET\s+['\"]([^'\"]+)['\"]\s+['\"]([^'\"]*)['\"]\s*$""",
    re.IGNORECASE | re.MULTILINE,
)

_PREFIX = "runtime.motor2."
_DOC_FIELDS = frozenset({"oql_alias", "notes", "oql-alias"})


def _scenarios_roots() -> list[Path]:
    roots: list[Path] = []
    for key in ("OQLOS_SCENARIOS_DIR", "OQLOS_SCENARIOS", "SCENARIOS_DIR"):
        raw = os.getenv(key, "").strip()
        if raw:
            roots.append(Path(raw).expanduser())
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / "oql-scenario",
        here.parents[2] / "scenarios",  # oqlos/scenarios submodule
        Path.home() / "oqlos" / "oql-scenario",
        Path("/home/pi/oqlos/oql-scenario"),
        Path("/home/tom/github/oqlos/oql-scenario"),
        Path("/home/tom/github/maskservice/c2004/extern/scenarios"),
    ]
    for path in candidates:
        if path not in roots:
            roots.append(path)
    return roots


def _profile_file_candidates() -> list[Path]:
    if os.getenv("OQLOS_MOTOR2_RUNTIME_DISABLE", "").strip() in {"1", "true", "yes"}:
        return []
    explicit = os.getenv("OQLOS_MOTOR2_RUNTIME_OQL", "").strip()
    files: list[Path] = []
    if explicit:
        for part in explicit.split(os.pathsep):
            part = part.strip()
            if part:
                files.append(Path(part).expanduser())
        return files
    rel = Path("layers/hardware/motor2-runtime.oql")
    seen: set[str] = set()
    for root in _scenarios_roots():
        path = root / rel
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        files.append(path)
    return files


def parse_motor2_sets(text: str) -> dict[str, str]:
    """Return raw SET key → value for runtime.motor2.* only."""
    values: dict[str, str] = {}
    for match in _SET_RE.finditer(text or ""):
        key = match.group(1).strip()
        val = match.group(2).strip()
        if key.startswith(_PREFIX):
            values[key] = val
    return values


def _coerce_value(field: str, raw: str) -> Any:
    token = str(raw or "").strip()
    if not token:
        return None
    # String fields
    if field in {
        "peripheralId",
        "speedUnit",
        "accelerationUnit",
        "limitMode",
        "startDirection",
    }:
        return token
    # Numeric int fields
    if field in {
        "strokeSteps",
        "maxStepsPerSecond",
        "defaultSpeedStepsPerSecond",
        "accelerationPercentPerSecond",
    }:
        try:
            return int(float(token))
        except (TypeError, ValueError):
            return None
    # Float
    if field in {"cycleVolumeLiters"}:
        try:
            return float(token)
        except (TypeError, ValueError):
            return None
    return token


def build_motor2_from_sets(sets: dict[str, str]) -> dict[str, Any]:
    motor2: dict[str, Any] = {}
    for key, val in sets.items():
        if not key.startswith(_PREFIX):
            continue
        field_raw = key[len(_PREFIX) :].strip()
        if not field_raw or field_raw.lower().replace("-", "_") in _DOC_FIELDS:
            continue
        field = canonicalize_motor2_runtime_key(field_raw)
        if field.lower().replace("-", "_") in _DOC_FIELDS:
            continue
        coerced = _coerce_value(field, val)
        if coerced is not None:
            motor2[field] = coerced
    return motor2


@lru_cache(maxsize=8)
def _load_sets_from_disk(signature: str) -> dict[str, str]:
    _ = signature
    merged: dict[str, str] = {}
    for path in _profile_file_candidates():
        try:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        merged.update(parse_motor2_sets(text))
    return merged


def _disk_signature() -> str:
    parts: list[str] = []
    for path in _profile_file_candidates():
        try:
            st = path.stat()
            parts.append(f"{path}:{st.st_mtime_ns}:{st.st_size}")
        except OSError:
            parts.append(f"{path}:missing")
    return "|".join(parts)


def load_oql_motor2_runtime() -> dict[str, Any]:
    """Return motor2 dict from OQL (may be empty)."""
    sets = _load_sets_from_disk(_disk_signature())
    return build_motor2_from_sets(sets)


def merge_motor2_runtime(map_motor2: dict[str, Any] | None, oql_motor2: dict[str, Any] | None) -> dict[str, Any]:
    """Merge MAP motor2 under OQL motor2 (OQL wins per key)."""
    base = dict(map_motor2 or {}) if isinstance(map_motor2, dict) else {}
    overlay = dict(oql_motor2 or {}) if isinstance(oql_motor2, dict) else {}
    if not base and not overlay:
        return {}
    # canonicalize keys from both
    out: dict[str, Any] = {}
    for k, v in base.items():
        out[canonicalize_motor2_runtime_key(str(k))] = v
    for k, v in overlay.items():
        out[canonicalize_motor2_runtime_key(str(k))] = v
    return out


def apply_oql_motor2_to_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    """In-place merge OQL motor2 into mapping['runtimeConfig']['motor2']. Returns mapping."""
    oql = load_oql_motor2_runtime()
    if not oql:
        return mapping
    runtime = mapping.get("runtimeConfig")
    if not isinstance(runtime, dict):
        runtime = {}
        mapping["runtimeConfig"] = runtime
    map_m2 = runtime.get("motor2") if isinstance(runtime.get("motor2"), dict) else {}
    runtime["motor2"] = merge_motor2_runtime(map_m2, oql)
    return mapping


def clear_oql_motor2_runtime_cache() -> None:
    _load_sets_from_disk.cache_clear()
