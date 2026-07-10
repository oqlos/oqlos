"""Shared pytest fixtures for the oqlos test suite."""

from __future__ import annotations

import pytest

from oqlos.api import hardware_runtime as runtime


@pytest.fixture(autouse=True)
def _reset_hardware_runtime_batch_cache():
    """Prevent cross-test pollution from cached gateway health."""
    runtime._BATCH_HEALTH_CACHE["expires_at"] = 0.0
    runtime._BATCH_HEALTH_CACHE["payload"] = None
    yield
    runtime._BATCH_HEALTH_CACHE["expires_at"] = 0.0
    runtime._BATCH_HEALTH_CACHE["payload"] = None
