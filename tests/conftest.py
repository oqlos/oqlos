"""Shared pytest fixtures for the oqlos test suite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# The c2004 workspace can also have an editable sibling OqlOS installed. Test
# this checkout explicitly; silently importing the sibling would validate code
# different from the submodule that is deployed to BoardNet.
OQLOS_CHECKOUT = Path(__file__).resolve().parents[1]
OQLOS_CORE_SRC = OQLOS_CHECKOUT / "packages" / "oqlos-core" / "src"
for source_root in (OQLOS_CORE_SRC, OQLOS_CHECKOUT):
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))

from oqlos.api import hardware_runtime as runtime


@pytest.fixture(autouse=True)
def _reset_hardware_runtime_batch_cache():
    """Prevent cross-test pollution from cached gateway health."""
    runtime._BATCH_HEALTH_CACHE["expires_at"] = 0.0
    runtime._BATCH_HEALTH_CACHE["payload"] = None
    yield
    runtime._BATCH_HEALTH_CACHE["expires_at"] = 0.0
    runtime._BATCH_HEALTH_CACHE["payload"] = None
