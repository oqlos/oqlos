"""Regression tests for extracted actuator and lung routes."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from oqlos.api import hardware as hw
from oqlos.api import hardware_actuators as actuators
from oqlos.api import hardware_lung as lung
from oqlos.api.hardware_lung import command_payload
from oqlos.errors import OqlosError


def _route_paths() -> set[str]:
    paths: set[str] = set()
    for route in hw.router.routes:
        path = getattr(route, "path", None)
        if isinstance(path, str):
            paths.add(path)
            continue
        nested = getattr(route, "original_router", None)
        for child in getattr(nested, "routes", []) or []:
            child_path = getattr(child, "path", None)
            if isinstance(child_path, str):
                paths.add(child_path)
    return paths


def test_hardware_router_includes_actuator_and_lung_paths():
    paths = _route_paths()
    assert "/valve/{valve_id}" in paths
    assert "/pump" in paths
    assert "/lung" in paths
    assert "/artificial-lung/status" in paths


def test_command_payload_requires_command_name():
    with pytest.raises(HTTPException) as exc:
        command_payload({})
    assert exc.value.status_code == 400


def test_set_pump_raises_typed_error_when_dri0050_unavailable(monkeypatch):
    class _Gateway:
        async def set_pump(self, power_pct: float):
            return {"success": False, "error": "Motor plugin not available"}

    monkeypatch.setattr(actuators, "get_hardware_gateway", lambda: _Gateway())

    with pytest.raises(OqlosError) as caught:
        asyncio.run(actuators.set_pump(12.5))
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "hw_dri0050_sidecar_unreachable"


def test_lung_stop_raises_typed_error_when_tic249_unavailable(monkeypatch):
    class _Gateway:
        async def stop_lung(self):
            return False

    monkeypatch.setattr(lung, "get_hardware_gateway", lambda: _Gateway())

    with pytest.raises(OqlosError) as caught:
        asyncio.run(lung.stop_lung())
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "hw_tic249_sidecar_unreachable"
