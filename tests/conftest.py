"""Shared pytest fixtures for the oqlos test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

# The c2004 workspace can also have an editable sibling OqlOS installed. The
# import provenance test below ensures that the configured test mode does not
# silently validate that sibling instead of this checkout.
OQLOS_CHECKOUT = Path(__file__).resolve().parents[1]

from oqlos.api import hardware_runtime as runtime


@pytest.fixture(autouse=True)
def _reset_hardware_runtime_batch_cache():
    """Prevent cross-test pollution from cached gateway health."""
    runtime._BATCH_HEALTH_CACHE["expires_at"] = 0.0
    runtime._BATCH_HEALTH_CACHE["payload"] = None
    yield
    runtime._BATCH_HEALTH_CACHE["expires_at"] = 0.0
    runtime._BATCH_HEALTH_CACHE["payload"] = None
