"""Tests for OQL-sourced HUI profiles (MAP → OQL migration slice 1)."""

from __future__ import annotations

from pathlib import Path

from oqlos.hardware import hui_hold, hui_valve
from oqlos.hardware.hui_profiles_oql import (
    build_hold_profiles_from_sets,
    build_valve_specs_from_sets,
    clear_oql_hui_profiles_cache,
    parse_hui_profile_sets,
)


SAMPLE = """
VERSION: 5
CONFIG:
  SET 'hui.hold.head-inflate.valves_on' 'valve-8,valve-1'
  SET 'hui.hold.head-inflate.pump_pct' '12.5'
  SET 'hui.valve.wc-press.valve_id' 'valve-99'
  SET 'hui.valve.wc-press.value' 'true'
  SET 'other.key' 'ignore'
"""


def test_parse_and_build_hold_profiles() -> None:
    sets = parse_hui_profile_sets(SAMPLE)
    assert "hui.hold.head-inflate.valves_on" in sets
    profiles = build_hold_profiles_from_sets(sets)
    assert profiles["head-inflate"]["valves_on"] == ("valve-8", "valve-1")
    assert profiles["head-inflate"]["pump_pct"] == 12.5


def test_parse_and_build_valve_specs() -> None:
    sets = parse_hui_profile_sets(SAMPLE)
    specs = build_valve_specs_from_sets(sets)
    assert specs["wc-press"] == {"valve_id": "valve-99", "value": True}


def test_oql_profiles_override_map_and_defaults(tmp_path: Path, monkeypatch) -> None:
    oql_file = tmp_path / "hui-profiles.oql"
    oql_file.write_text(SAMPLE, encoding="utf-8")
    monkeypatch.setenv("OQLOS_HUI_PROFILES_OQL", str(oql_file))
    clear_oql_hui_profiles_cache()

    monkeypatch.setattr(
        hui_hold,
        "_mapped_hui_hold_profiles",
        lambda: {"head-inflate": {"valves_on": ("valve-5", "valve-2"), "pump_pct": 70.0}},
    )
    profiles = hui_hold.get_hui_hold_profiles()
    assert profiles["head-inflate"]["valves_on"] == ("valve-8", "valve-1")
    assert profiles["head-inflate"]["pump_pct"] == 12.5

    monkeypatch.setattr(
        hui_valve,
        "_mapped_hui_valve_specs",
        lambda: {"wc-press": {"valve_id": "valve-wc", "value": True}},
    )
    specs = hui_valve.get_hui_valve_specs()
    assert specs["wc-press"]["valve_id"] == "valve-99"

    clear_oql_hui_profiles_cache()
