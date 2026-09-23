"""Load HUI hold/valve/lung recipes from OQL SET keys.

Source file (default): ``layers/hardware/hui-profiles.oql`` under
``OQLOS_SCENARIOS_DIR`` (or paths listed in ``OQLOS_HUI_PROFILES_OQL``).

Keys:
  hui.hold.<key>.valves_on   = comma-separated valve ids
  hui.hold.<key>.pump_pct    = float
  hui.hold.<key>.valve_stagger_ms = integer 100..1000 (default 100)
  hui.valve.<key>.valve_id   = valve id
  hui.valve.<key>.value      = true|false|on|off
  hui.lung.<field>            = artificial-lung motion/stop setting
"""

from __future__ import annotations

import json
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
_TIMING_PREFIX = "hui.timing."
_LEASE_PREFIX = "hui.lease."
_DISCOVERY_PREFIX = "hui.discovery."


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
        if key.startswith((_HOLD_PREFIX, _VALVE_PREFIX, _LUNG_PREFIX, _TIMING_PREFIX, _LEASE_PREFIX, _DISCOVERY_PREFIX, "hui.", "maskauth.", "stacknet.")):
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
        elif field == "valve_stagger_ms":
            try:
                stagger = int(str(val).strip())
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} must be an integer in 0..2000 ms") from exc
            if not 0 <= stagger <= 2000:
                raise ValueError(f"{key} must be in 0..2000 ms")
            bucket[field] = stagger
    profiles: dict[str, dict[str, Any]] = {}
    for hold_key, bucket in buckets.items():
        if "valves_on" in bucket and "pump_pct" in bucket:
            profiles[hold_key] = {
                "valves_on": tuple(bucket["valves_on"]),
                "pump_pct": float(bucket["pump_pct"]),
            }
            if "valve_stagger_ms" in bucket:
                profiles[hold_key]["valve_stagger_ms"] = bucket["valve_stagger_ms"]
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
    non_negative_integer_fields = {"cycles"}
    positive_integer_fields = {
        "steps",
        "stroke_steps",
        "speed_steps_per_second",
        "max_steps_per_second",
        "rearm_steps",
        "rearm_speed_steps_per_second",
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
        elif field in non_negative_integer_fields:
            try:
                value = int(str(val).strip())
            except (TypeError, ValueError):
                continue
            if value >= 0:
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


def _load_sets_from_db() -> dict[str, str]:
    db_url = os.getenv("CONFIG_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        return {}
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(db_url)
        with engine.connect() as conn:
            row = conn.execute(text("SELECT data FROM config_sections WHERE section = 'hardware-hui-config'")).fetchone()
            if not row or not row[0]:
                return {}
            data = json.loads(row[0])
            db_sets: dict[str, str] = {}
            if "timing" in data and isinstance(data["timing"], dict):
                t = data["timing"]
                if "min_hold_ms" in t:
                    db_sets["hui.timing.min_hold_ms"] = str(t["min_hold_ms"])
                if "valve_stagger_ms" in t:
                    db_sets["hui.timing.valve_stagger_ms"] = str(t["valve_stagger_ms"])
                if "skip_idle_pump_off" in t:
                    db_sets["hui.timing.skip_idle_pump_off"] = str(t["skip_idle_pump_off"])
            if "lease" in data and isinstance(data["lease"], dict):
                l = data["lease"]
                if "ttl_ms" in l:
                    db_sets["hui.lease.ttl_ms"] = str(l["ttl_ms"])
                if "renew_interval_seconds" in l:
                    db_sets["hui.lease.renew_interval_seconds"] = str(l["renew_interval_seconds"])
                if "reuse_active" in l:
                    db_sets["hui.lease.reuse_active"] = str(l["reuse_active"])
            if "discovery" in data and isinstance(data["discovery"], dict):
                d = data["discovery"]
                if "ttl_seconds" in d:
                    db_sets["hui.discovery.ttl_seconds"] = str(d["ttl_seconds"])
            if "capability" in data and isinstance(data["capability"], dict):
                c = data["capability"]
                if "token_ttl_seconds" in c:
                    db_sets["hui.capability.token_ttl_seconds"] = str(c["token_ttl_seconds"])
            if "lung" in data and isinstance(data["lung"], dict):
                for k, v in data["lung"].items():
                    db_sets[f"hui.lung.{k}"] = str(v)
            if "holds" in data and isinstance(data["holds"], dict):
                for hold_name, hold_cfg in data["holds"].items():
                    if isinstance(hold_cfg, dict):
                        if "valves" in hold_cfg:
                            valves_val = hold_cfg["valves"]
                            if isinstance(valves_val, list):
                                valves_val = ",".join(str(x) for x in valves_val)
                            db_sets[f"hui.hold.{hold_name}.valves_on"] = str(valves_val)
                        if "pump_pct" in hold_cfg:
                            db_sets[f"hui.hold.{hold_name}.pump_pct"] = str(hold_cfg["pump_pct"])
            return db_sets
    except Exception:
        return {}


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
    # Overlay dynamic system configuration from database when available
    merged.update(_load_sets_from_db())
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


def build_timing_config_from_sets(sets: dict[str, str]) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "valve_stagger_ms": 100,
        "min_hold_ms": 0,
        "skip_idle_pump_off": True,
        "lease_ttl_ms": 5000,
        "lease_renew_interval_seconds": 1.5,
        "lease_reuse_active": True,
        "discovery_ttl_seconds": 60.0,
        "capability_token_ttl_seconds": 3600,
    }
    for key, val in sets.items():
        if key in {"hui.timing.valve_stagger_ms", "hui.valve_stagger_ms"}:
            try:
                v = int(str(val).strip())
                if 0 <= v <= 2000:
                    cfg["valve_stagger_ms"] = v
            except (TypeError, ValueError):
                pass
        elif key in {"hui.timing.min_hold_ms", "hui.min_hold_ms"}:
            try:
                v = int(str(val).strip())
                if 0 <= v <= 10000:
                    cfg["min_hold_ms"] = v
            except (TypeError, ValueError):
                pass
        elif key in {"hui.timing.skip_idle_pump_off", "hui.skip_idle_pump_off"}:
            b = _coerce_bool(val)
            if b is not None:
                cfg["skip_idle_pump_off"] = b
        elif key in {"hui.lease.ttl_ms", "stacknet.lease.ttl_ms"}:
            try:
                v = int(str(val).strip())
                if 500 <= v <= 60000:
                    cfg["lease_ttl_ms"] = v
            except (TypeError, ValueError):
                pass
        elif key in {"hui.lease.renew_interval_seconds", "hui.lease.renew_interval"}:
            f = _coerce_float(val)
            if f is not None and 0.1 <= f <= 30.0:
                cfg["lease_renew_interval_seconds"] = f
        elif key in {"hui.lease.reuse_active", "stacknet.lease.reuse_active"}:
            b = _coerce_bool(val)
            if b is not None:
                cfg["lease_reuse_active"] = b
        elif key in {"hui.discovery.ttl_seconds", "stacknet.discovery.ttl_seconds", "fleet.discovery_ttl_seconds"}:
            f = _coerce_float(val)
            if f is not None and 1.0 <= f <= 3600.0:
                cfg["discovery_ttl_seconds"] = f
        elif key in {"hui.capability.token_ttl_seconds", "maskauth.capability_token_ttl_seconds", "hui.token_ttl_seconds"}:
            try:
                v = int(str(val).strip())
                if 30 <= v <= 86400:
                    cfg["capability_token_ttl_seconds"] = v
            except (TypeError, ValueError):
                pass
    return cfg


def load_oql_hui_timing_config() -> dict[str, Any]:
    sets = _load_sets_from_disk(_disk_signature())
    return build_timing_config_from_sets(sets)


def get_hui_default_valve_stagger_ms() -> int:
    return load_oql_hui_timing_config()["valve_stagger_ms"]


def get_hui_min_hold_ms() -> int:
    return load_oql_hui_timing_config()["min_hold_ms"]


def get_hui_skip_idle_pump_off() -> bool:
    return load_oql_hui_timing_config()["skip_idle_pump_off"]


def get_hui_lease_ttl_ms() -> int:
    return load_oql_hui_timing_config()["lease_ttl_ms"]


def get_hui_lease_renew_interval() -> float:
    return load_oql_hui_timing_config()["lease_renew_interval_seconds"]


def get_hui_lease_reuse_active() -> bool:
    return load_oql_hui_timing_config()["lease_reuse_active"]


def get_hui_discovery_ttl_seconds() -> float:
    return load_oql_hui_timing_config()["discovery_ttl_seconds"]


def get_hui_capability_token_ttl_seconds() -> int:
    return load_oql_hui_timing_config()["capability_token_ttl_seconds"]


def clear_oql_hui_profiles_cache() -> None:
    _load_sets_from_disk.cache_clear()
