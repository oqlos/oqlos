"""Tests for OQL-sourced HUI profiles (MAP → OQL migration slice 1)."""

from __future__ import annotations

from pathlib import Path

from oqlos.hardware import hui_hold, hui_lung_recipe, hui_valve
from oqlos.hardware.hui_profiles_oql import (
    build_hold_profiles_from_sets,
    build_lung_profile_from_sets,
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
  SET 'hui.lung.valve_id' 'valve-8'
  SET 'hui.lung.stroke_steps' '2500'
  SET 'hui.lung.speed_steps_per_second' '12000'
  SET 'hui.lung.max_steps_per_second' '12000'
  SET 'hui.lung.ramp_seconds' '0.25'
  SET 'hui.lung.pause' '0.1'
  SET 'hui.lung.cycles' '20'
  SET 'hui.lung.stop_at_limit' 'false'
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


def test_parse_and_build_lung_profile() -> None:
    sets = parse_hui_profile_sets(SAMPLE)
    profile = build_lung_profile_from_sets(sets)
    assert profile == {
        "valve_id": "valve-8",
        "stroke_steps": 2500,
        "speed_steps_per_second": 12000,
        "max_steps_per_second": 12000,
        "ramp_seconds": 0.25,
        "pause": 0.1,
        "cycles": 20,
        "stop_at_limit": False,
    }


def test_oql_profiles_override_normalized_config_and_defaults(tmp_path: Path, monkeypatch) -> None:
    oql_file = tmp_path / "hui-profiles.oql"
    oql_file.write_text(SAMPLE, encoding="utf-8")
    monkeypatch.setenv("OQLOS_HUI_PROFILES_OQL", str(oql_file))
    clear_oql_hui_profiles_cache()

    monkeypatch.setattr(
        hui_hold,
        "_configured_hui_hold_profiles",
        lambda: {"head-inflate": {"valves_on": ("valve-5", "valve-2"), "pump_pct": 70.0}},
    )
    profiles = hui_hold.get_hui_hold_profiles()
    assert profiles["head-inflate"]["valves_on"] == ("valve-8", "valve-1")
    assert profiles["head-inflate"]["pump_pct"] == 12.5

    monkeypatch.setattr(
        hui_valve,
        "_configured_hui_valve_specs",
        lambda: {"wc-press": {"valve_id": "valve-wc", "value": True}},
    )
    specs = hui_valve.get_hui_valve_specs()
    assert specs["wc-press"]["valve_id"] == "valve-99"

    monkeypatch.setattr(hui_lung_recipe, "_configured_hui_lung_profile", lambda: {})
    args = hui_lung_recipe.get_hui_lung_reciprocate_args()
    assert hui_lung_recipe.get_hui_lung_valve_id() == "valve-8"
    assert args["stroke_steps"] == 2500
    assert args["speed"] == 120_000_000
    assert args["ramp_seconds"] == 0.25
    assert args["pause"] == 0.1
    assert hui_lung_recipe.get_hui_lung_stop_at_limit(fallback=True) is False

    clear_oql_hui_profiles_cache()
