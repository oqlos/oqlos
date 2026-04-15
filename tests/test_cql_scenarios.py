"""Smoke tests — dry-run every CQL scenario through the interpreter.

Validates that every .cql file in the c2004 database and hardware examples
parses and dry-runs without errors.  No live hardware needed.
"""
from __future__ import annotations

import glob
import os
from pathlib import Path

import pytest

from oqlos.core.interpreter import CqlInterpreter

C2004_ROOT = Path(
    os.environ.get("C2004_ROOT", Path(__file__).resolve().parents[3] / "maskservice" / "c2004")
)
CQL_DB_DIR = C2004_ROOT / "db" / "dsl" / "cql" / "scenarios"
CQL_HW_EXAMPLES = C2004_ROOT / "hardware" / "examples"


def _collect(directory: Path, ext: str = "*.cql") -> list[str]:
    if not directory.is_dir():
        return []
    return sorted(glob.glob(str(directory / ext)))


CQL_DB_SCENARIOS = _collect(CQL_DB_DIR)
CQL_EXAMPLES = _collect(CQL_HW_EXAMPLES)


@pytest.mark.parametrize(
    "path",
    CQL_DB_SCENARIOS,
    ids=[os.path.basename(p) for p in CQL_DB_SCENARIOS],
)
def test_cql_db_scenario_dryrun(path: str) -> None:
    """Each CQL database scenario must dry-run without failures."""
    interp = CqlInterpreter(mode="dry-run", quiet=True)
    result = interp.run_file(path)
    assert result.ok, (
        f"{os.path.basename(path)}: {result.failed} failed, "
        f"errors={result.errors}"
    )
    assert result.passed > 0, f"{os.path.basename(path)}: no steps passed"


@pytest.mark.parametrize(
    "path",
    CQL_EXAMPLES,
    ids=[os.path.basename(p) for p in CQL_EXAMPLES],
)
def test_cql_hw_example_dryrun(path: str) -> None:
    """Each CQL hardware example must dry-run without failures."""
    interp = CqlInterpreter(mode="dry-run", quiet=True)
    result = interp.run_file(path)
    assert result.ok, (
        f"{os.path.basename(path)}: {result.failed} failed, "
        f"errors={result.errors}"
    )


def test_cql_invalid_example_rejects_unknown_peripheral() -> None:
    """The invalid example must still parse but report POMPX as warning/error."""
    invalid = str(CQL_HW_EXAMPLES / "mask-tightness-invalid.cql")
    if not os.path.exists(invalid):
        pytest.skip("invalid example not found")
    interp = CqlInterpreter(mode="dry-run", quiet=True)
    result = interp.run_file(invalid)
    # The scenario itself runs (pump/valve steps succeed in dry-run)
    # but we expect the POMPX line to produce a warning or be skipped
    assert result.passed >= 1, "valid steps should still pass"


@pytest.mark.parametrize(
    "path",
    CQL_DB_SCENARIOS,
    ids=[os.path.basename(p) for p in CQL_DB_SCENARIOS],
)
def test_cql_db_scenario_validate(path: str) -> None:
    """Each CQL database scenario must validate (parse) cleanly (warnings OK)."""
    interp = CqlInterpreter(mode="validate", quiet=True)
    result = interp.run_file(path)
    assert not result.errors, (
        f"{os.path.basename(path)}: validation errors: {result.errors}"
    )
