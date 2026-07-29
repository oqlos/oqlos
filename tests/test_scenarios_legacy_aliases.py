import json
import os
from pathlib import Path

from oqlos.scenarios.legacy_aliases import LEGACY_SCENARIO_ALIASES, resolve_canonical_scenario_file


def _scenarios_dir() -> Path:
    repo = Path(__file__).resolve().parents[1]
    return Path(os.environ.get("OQLOS_SCENARIOS_DIR", repo.parent / "oql-scenario"))


def test_legacy_alias_map_covers_renamed_exports():
    scenarios = _scenarios_dir()
    alias_file = scenarios / "legacy_aliases.json"
    assert alias_file.is_file()
    assert json.loads(alias_file.read_text(encoding="utf-8")) == LEGACY_SCENARIO_ALIASES
    assert LEGACY_SCENARIO_ALIASES
    for legacy, canonical in LEGACY_SCENARIO_ALIASES.items():
        assert (scenarios / canonical).is_file(), f"missing canonical {canonical} for {legacy}"
        resolved = resolve_canonical_scenario_file(legacy, scenarios)
        assert resolved == scenarios / canonical


def test_scenarios_root_has_no_ts_prefix_files():
    root_ts = list(_scenarios_dir().glob("ts-*.oql"))
    assert root_ts == [], f"legacy ts-* still in scenarios root: {root_ts}"
