"""Validate and atomically persist the live BoardNet HUI OQL profile."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from oqlos.hardware.hui_lung_recipe import get_hui_lung_reciprocate_args
from oqlos.hardware.hui_profiles_oql import (
    build_lung_profile_from_sets,
    clear_oql_hui_profiles_cache,
    parse_hui_profile_sets,
    resolve_oql_hui_profiles_path,
)

HUI_LUNG_SAFE_MAX_STEPS_PER_SECOND = 12_000
_MAX_SOURCE_BYTES = 256 * 1024
_VERSION_RE = re.compile(r"^\s*VERSION\s*:\s*6\s*$", re.IGNORECASE | re.MULTILINE)


class HuiProfileSourceError(ValueError):
    """The proposed HUI profile is invalid or unsafe."""


def validate_hui_profile_source(content: str) -> dict[str, Any]:
    """Return the parsed lung profile after syntax and motion safety checks."""
    source = str(content or "")
    if not source.strip():
        raise HuiProfileSourceError("HUI profile source must not be empty")
    if len(source.encode("utf-8")) > _MAX_SOURCE_BYTES:
        raise HuiProfileSourceError("HUI profile source is too large")
    if not _VERSION_RE.search(source):
        raise HuiProfileSourceError("HUI profile must declare VERSION: 6")
    if not re.search(r"^\s*CONFIG\s*:\s*$", source, re.IGNORECASE | re.MULTILINE):
        raise HuiProfileSourceError("HUI profile must contain CONFIG:")

    sets = parse_hui_profile_sets(source)
    lung = build_lung_profile_from_sets(sets)
    required = ("speed_steps_per_second", "max_steps_per_second", "pause")
    missing = [field for field in required if field not in lung]
    if missing:
        raise HuiProfileSourceError(
            f"Missing or invalid HUI lung setting(s): {', '.join(missing)}"
        )

    speed = int(lung["speed_steps_per_second"])
    maximum = int(lung["max_steps_per_second"])
    if maximum > HUI_LUNG_SAFE_MAX_STEPS_PER_SECOND:
        raise HuiProfileSourceError(
            "hui.lung.max_steps_per_second must not exceed "
            f"{HUI_LUNG_SAFE_MAX_STEPS_PER_SECOND}"
        )
    if speed > maximum:
        raise HuiProfileSourceError(
            "hui.lung.speed_steps_per_second must not exceed max_steps_per_second"
        )
    return lung


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = content if content.endswith("\n") else f"{content}\n"
    fd, raw_temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(raw_temp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(normalized)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(temp_path, path.stat().st_mode & 0o777)
        os.replace(temp_path, path)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def persist_hui_profile_source(content: str) -> dict[str, Any]:
    """Validate, atomically persist and expose the effective next-START recipe."""
    lung = validate_hui_profile_source(content)
    target = resolve_oql_hui_profiles_path()
    _atomic_write(target, content)
    clear_oql_hui_profiles_cache()
    effective = get_hui_lung_reciprocate_args()
    normalized = content if content.endswith("\n") else f"{content}\n"
    return {
        "path": str(target),
        "sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "configured": lung,
        "effective": effective,
    }
