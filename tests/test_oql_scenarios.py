"""Smoke tests — dry-run every OQL scenario through the interpreter.

Validates that every .oql file in the oqlos scenarios directory parses
and dry-runs without errors.  These tests do NOT require live hardware.
"""
from __future__ import annotations

import glob
import os
from pathlib import Path

import pytest

from oqlos.core.interpreter import CqlInterpreter

SCENARIOS_DIR = Path(__file__).resolve().parents[1] / "scenarios"
EXAMPLES_DIR = SCENARIOS_DIR / "examples"


def _collect(directory: Path, ext: str = "*.oql") -> list[str]:
    """Collect scenario files from a directory."""
    if not directory.is_dir():
        return []
    return sorted(glob.glob(str(directory / ext)))


OQL_SCENARIOS = _collect(SCENARIOS_DIR)
OQL_EXAMPLES = _collect(EXAMPLES_DIR)


@pytest.mark.parametrize(
    "path",
    OQL_SCENARIOS,
    ids=[os.path.basename(p) for p in OQL_SCENARIOS],
)
def test_oql_scenario_dryrun(path: str) -> None:
    """Each OQL scenario must dry-run without failures."""
    interp = CqlInterpreter(mode="dry-run", quiet=True)
    result = interp.run_file(path)
    assert result.ok, (
        f"{os.path.basename(path)}: {result.failed} failed, "
        f"errors={result.errors}"
    )
    assert result.passed > 0, f"{os.path.basename(path)}: no steps passed"


@pytest.mark.parametrize(
    "path",
    OQL_EXAMPLES,
    ids=[os.path.basename(p) for p in OQL_EXAMPLES],
)
def test_oql_example_dryrun(path: str) -> None:
    """Each OQL config example must dry-run without failures."""
    interp = CqlInterpreter(mode="dry-run", quiet=True)
    result = interp.run_file(path)
    assert result.ok, (
        f"{os.path.basename(path)}: {result.failed} failed, "
        f"errors={result.errors}"
    )


@pytest.mark.parametrize(
    "path",
    OQL_SCENARIOS,
    ids=[os.path.basename(p) for p in OQL_SCENARIOS],
)
def test_oql_scenario_validate(path: str) -> None:
    """Each OQL scenario must parse/validate cleanly (warnings are acceptable)."""
    interp = CqlInterpreter(mode="validate", quiet=True)
    result = interp.run_file(path)
    assert not result.errors, (
        f"{os.path.basename(path)}: validation errors: {result.errors}"
    )
