"""Regression: OqlOS reads the standalone sibling scenario repository."""

from __future__ import annotations

from pathlib import Path

from oqlos.api.editor import _default_scenarios_dir
from oqlos.core._oql_adapter import _scenarios_root


def test_default_scenarios_dir_points_at_repo_root():
    repo_root = Path(__file__).resolve().parents[1]
    expected = repo_root.parent / "oql-scenario"
    assert _default_scenarios_dir() == expected
    assert _scenarios_root() == expected
    assert (expected / "kalibracja-czujnikow.oql").is_file()
    assert (expected / "archive" / "ts-export-2026-04-30" / "ts-flow.oql").is_file()
