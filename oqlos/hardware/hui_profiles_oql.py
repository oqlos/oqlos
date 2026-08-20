"""Load HUI hold/valve/lung recipes from OQL SET keys.

Source file (default): ``layers/hardware/hui-profiles.oql`` under
``OQLOS_SCENARIOS_DIR`` (or paths listed in ``OQLOS_HUI_PROFILES_OQL``).

Keys:
  hui.hold.<key>.valves_on   = comma-separated valve ids
  hui.hold.<key>.pump_pct    = float
  hui.valve.<key>.valve_id   = valve id
  hui.valve.<key>.value      = true|false|on|off
  hui.lung.<field>            = artificial-lung motion/stop setting
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_SET_RE = re.compile(
    r"""^\s*SET\s+['\"]([^'\"]+)['\"]\s+['\"]([^'\"]*)['\"]\s*$""",
    re.IGNORECASE | re.MULTILINE,
)

_HOLD_PREFIX = "hui.hold."
_VALVE_PREFIX = "hui.valve."
_LUNG_PREFIX = "hui.lung."


def _scenarios_roots() -> list[Path]:
    roots: list[Path] = []
    for key in ("OQLOS_SCENARIOS_DIR", "OQLOS_SCENARIOS", "SCENARIOS_DIR"):
        raw = os.getenv(key, "").strip()
        if raw:
            roots.append(Path(raw).expanduser())
    # Common checkouts relative to this package / home
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / "oql-scenario",  # repo sibling when monorepo-ish
        Path.home() / "oqlos" / "oql-scenario",
        Path("/home/pi/oqlos/oql-scenario"),
    ]
    for path in candidates:
        if path not in roots:
            roots.append(path)
    return roots


def _profile_file_candidates() -> list[Path]:
    if os.getenv("OQLOS_HUI_PROFILES_DISABLE", "").strip() in {"1", "true", "yes"}:
        return []
    explicit = os.getenv("OQLOS_HUI_PROFILES_OQL", "").strip()
    files: list[Path] = []
    if explicit:
        # Explicit list is exclusive (tests / single-file override).
        for part in explicit.split(os.pathsep):
            part = part.strip()
            if part:
                files.append(Path(part).expanduser())
        return files
    rel = Path("layers/hardware/hui-profiles.oql")
    for root in _scenarios_roots():
        files.append(root / rel)
    # de-dupe preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for path in files:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def resolve_oql_hui_profiles_path() -> Path:
    """Return the profile source used by this runtime, preferring an existing file."""
    candidates = _profile_file_candidates()
    if not candidates:
        raise FileNotFoundError("OQL HUI profiles are disabled")
    return next((path for path in candidates if path.is_file()), candidates[0])


def parse_hui_profile_sets(text: str) -> dict[str, str]:
    """Return raw SET key → value map for supported HUI profile keys."""
    values: dict[str, str] = {}
    for match in _SET_RE.finditer(text or ""):
        key = match.group(1).strip()
        val = match.group(2).strip()
        if key.startswith((_HOLD_PREFIX, _VALVE_PREFIX, _LUNG_PREFIX)):
            values[key] = val
    return values


def _coerce_valves(raw: str) -> tuple[str, ...] | None:
    items = [part.strip() for part in str(raw or "").split(",")]
    valves = tuple(item for item in items if item)
    return valves or None


def _coerce_float(raw: str) -> float | None:
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _coerce_bool(raw: str) -> bool | None:
    token = str(raw or "").strip().lower()
    if token in {"1", "true", "on", "open", "press"}:
        return True
    if token in {"0", "false", "off", "close", "bleed"}:
        return False
    return None


def build_hold_profiles_from_sets(sets: dict[str, str]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for key, val in sets.items():
        if not key.startswith(_HOLD_PREFIX):
            continue
        rest = key[len(_HOLD_PREFIX) :]
        if "." not in rest:
            continue
        hold_key, field = rest.rsplit(".", 1)
        hold_key = hold_key.strip().lower()
        field = field.strip().lower()
        if not hold_key:
            continue
        bucket = buckets.setdefault(hold_key, {})
        if field in {"valves_on", "valves"}:
            valves = _coerce_valves(val)
            if valves is not None:
                bucket["valves_on"] = valves
        elif field in {"pump_pct", "pump", "power_pct"}:
            pump = _coerce_float(val)
            if pump is not None:
                bucket["pump_pct"] = pump
    profiles: dict[str, dict[str, Any]] = {}
    for hold_key, bucket in buckets.items():
        if "valves_on" in bucket and "pump_pct" in bucket:
            profiles[hold_key] = {
                "valves_on": tuple(bucket["valves_on"]),
                "pump_pct": float(bucket["pump_pct"]),
            }
    return profiles


def build_valve_specs_from_sets(sets: dict[str, str]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for key, val in sets.items():
        if not key.startswith(_VALVE_PREFIX):
            continue
        rest = key[len(_VALVE_PREFIX) :]
        if "." not in rest:
            continue
        valve_key, field = rest.rsplit(".", 1)
        valve_key = valve_key.strip().lower()
        field = field.strip().lower()
        if not valve_key:
            continue
        bucket = buckets.setdefault(valve_key, {})
        if field in {"valve_id", "valve"}:
            vid = str(val or "").strip()
            if vid:
                bucket["valve_id"] = vid
        elif field in {"value", "on", "open"}:
            flag = _coerce_bool(val)
            if flag is not None:
                bucket["value"] = flag
    specs: dict[str, dict[str, Any]] = {}
    for valve_key, bucket in buckets.items():
        if "valve_id" in bucket and "value" in bucket:
            specs[valve_key] = {
                "valve_id": str(bucket["valve_id"]),
                "value": bool(bucket["value"]),
            }
    return specs


def build_lung_profile_from_sets(sets: dict[str, str]) -> dict[str, Any]:
    """Build a partial artificial-lung profile from human-readable OQL values."""
    profile: dict[str, Any] = {}
    text_fields = {"valve_id", "direction", "start_direction", "limit_mode"}
    positive_integer_fields = {
        "steps",
        "stroke_steps",
        "speed_steps_per_second",
        "max_steps_per_second",
        "cycles",
    }
    non_negative_float_fields = {"pause", "ramp_seconds"}

    for key, val in sets.items():
        if not key.startswith(_LUNG_PREFIX):
            continue
        field = key[len(_LUNG_PREFIX) :].strip().lower()
        if field in text_fields:
            value = str(val or "").strip()
            if value:
                profile[field] = value
        elif field in positive_integer_fields:
            try:
                value = int(str(val).strip())
            except (TypeError, ValueError):
                continue
            if value > 0:
                profile[field] = value
        elif field in non_negative_float_fields:
            value = _coerce_float(val)
            if value is not None and value >= 0:
                profile[field] = value
        elif field == "stop_at_limit":
            value = _coerce_bool(val)
            if value is not None:
                profile[field] = value
    return profile


@lru_cache(maxsize=8)
def _load_sets_from_disk(signature: str) -> dict[str, str]:
    # signature forces cache bust when mtimes change
    _ = signature
    merged: dict[str, str] = {}
    for path in _profile_file_candidates():
        try:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        merged.update(parse_hui_profile_sets(text))
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


def load_oql_hui_hold_profiles() -> dict[str, dict[str, Any]]:
    sets = _load_sets_from_disk(_disk_signature())
    return build_hold_profiles_from_sets(sets)


def load_oql_hui_valve_specs() -> dict[str, dict[str, Any]]:
    sets = _load_sets_from_disk(_disk_signature())
    return build_valve_specs_from_sets(sets)


def load_oql_hui_lung_profile() -> dict[str, Any]:
    sets = _load_sets_from_disk(_disk_signature())
    return build_lung_profile_from_sets(sets)


def clear_oql_hui_profiles_cache() -> None:
    _load_sets_from_disk.cache_clear()
