"""Map legacy connect-data scenario ids/filenames to canonical ``oql-scenario/`` files."""

from __future__ import annotations

import json
import os
from pathlib import Path


def _repo_scenarios_dir() -> Path:
    override = os.environ.get("OQLOS_SCENARIOS_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "oql-scenario"


def _load_legacy_aliases() -> dict[str, str]:
    path = _repo_scenarios_dir() / "legacy_aliases.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


LEGACY_SCENARIO_ALIASES: dict[str, str] = _load_legacy_aliases()


def resolve_canonical_scenario_file(scenario_id: str, scenarios_dir: Path) -> Path | None:
    """Return canonical ``.oql`` path for a scenario id or basename."""
    key = scenario_id.strip()
    if key.endswith(".oql"):
        key = key[:-4]
    candidates = [key + ".oql"]
    alias = LEGACY_SCENARIO_ALIASES.get(key)
    if alias:
        candidates.insert(0, alias)
    for name in candidates:
        path = scenarios_dir / name
        if path.is_file():
            return path
    return None
