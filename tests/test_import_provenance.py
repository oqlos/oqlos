"""Prove which OqlOS installation is exercised by the test gate."""

from __future__ import annotations

import os
from pathlib import Path

import oqlos
import oqlos.core._action_motor2 as motor2_actions


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_SRC_ROOT = REPO_ROOT / "packages" / "oqlos-core" / "src"


def _resolved_module_path(module) -> Path:
    module_path = getattr(module, "__file__", None)
    assert module_path is not None
    return Path(module_path).resolve()


def test_oqlos_import_provenance() -> None:
    """Source and wheel gates must both prove their expected import origin."""
    oqlos_path = _resolved_module_path(oqlos)
    core_path = _resolved_module_path(motor2_actions)

    if os.environ.get("OQLOS_TEST_INSTALLED_WHEEL") == "1":
        assert not oqlos_path.is_relative_to(REPO_ROOT), oqlos_path
        assert not core_path.is_relative_to(REPO_ROOT), core_path
        assert "site-packages" in oqlos_path.parts, oqlos_path
        assert "site-packages" in core_path.parts, core_path
        return

    assert oqlos_path.is_relative_to(REPO_ROOT / "oqlos"), oqlos_path
    assert core_path.is_relative_to(CORE_SRC_ROOT), core_path
