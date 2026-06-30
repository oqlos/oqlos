from pathlib import Path

from oqlos.scenarios.legacy_aliases import LEGACY_SCENARIO_ALIASES, resolve_canonical_scenario_file


def test_legacy_alias_map_covers_renamed_exports():
    repo = Path(__file__).resolve().parents[1]
    scenarios = repo / "scenarios"
    for legacy, canonical in LEGACY_SCENARIO_ALIASES.items():
        assert (scenarios / canonical).is_file(), f"missing canonical {canonical} for {legacy}"
        resolved = resolve_canonical_scenario_file(legacy, scenarios)
        assert resolved == scenarios / canonical


def test_scenarios_root_has_no_ts_prefix_files():
    repo = Path(__file__).resolve().parents[1]
    root_ts = list((repo / "scenarios").glob("ts-*.oql"))
    assert root_ts == [], f"legacy ts-* still in scenarios root: {root_ts}"
