"""Tests for OQL-sourced motor2 runtime (MAP → OQL migration slice 2d)."""

from __future__ import annotations

from pathlib import Path

from oqlos.hardware.motor2_runtime_oql import (
    apply_oql_motor2_to_mapping,
    build_motor2_from_sets,
    clear_oql_motor2_runtime_cache,
    merge_motor2_runtime,
    parse_motor2_sets,
)


SAMPLE = """
VERSION: 5
CONFIG:
  SET 'runtime.motor2.peripheralId' 'motor-tic249'
  SET 'runtime.motor2.strokeSteps' '500'
  SET 'runtime.motor2.cycleVolumeLiters' '2.5'
  SET 'runtime.motor2.maxStepsPerSecond' '800'
  SET 'runtime.motor2.defaultSpeedStepsPerSecond' '400'
  SET 'runtime.motor2.startDirection' 'left'
  SET 'runtime.motor2.notes' 'ignore doc'
  SET 'other.key' 'ignore'
"""


def test_parse_and_build_motor2() -> None:
    sets = parse_motor2_sets(SAMPLE)
    assert "runtime.motor2.strokeSteps" in sets
    motor2 = build_motor2_from_sets(sets)
    assert motor2["peripheralId"] == "motor-tic249"
    assert motor2["strokeSteps"] == 500
    assert motor2["cycleVolumeLiters"] == 2.5
    assert motor2["maxStepsPerSecond"] == 800
    assert motor2["defaultSpeedStepsPerSecond"] == 400
    assert motor2["startDirection"] == "left"
    assert "notes" not in motor2


def test_merge_oql_wins_over_map() -> None:
    merged = merge_motor2_runtime(
        {"strokeSteps": 1000, "startDirection": "right", "speedUnit": "steps/s"},
        {"strokeSteps": 500, "startDirection": "left"},
    )
    assert merged["strokeSteps"] == 500
    assert merged["startDirection"] == "left"
    assert merged["speedUnit"] == "steps/s"


def test_apply_oql_to_mapping(tmp_path: Path, monkeypatch) -> None:
    oql_file = tmp_path / "motor2-runtime.oql"
    oql_file.write_text(SAMPLE, encoding="utf-8")
    monkeypatch.setenv("OQLOS_MOTOR2_RUNTIME_OQL", str(oql_file))
    clear_oql_motor2_runtime_cache()

    mapping = {
        "runtimeConfig": {
            "motor2": {
                "peripheralId": "motor-tic249",
                "strokeSteps": 1000,
                "startDirection": "right",
            }
        }
    }
    apply_oql_motor2_to_mapping(mapping)
    m2 = mapping["runtimeConfig"]["motor2"]
    assert m2["strokeSteps"] == 500
    assert m2["startDirection"] == "left"
    assert m2["cycleVolumeLiters"] == 2.5

    clear_oql_motor2_runtime_cache()
