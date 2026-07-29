"""Regression tests for extracted actuator and lung routes."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oqlos.api import hardware as hw
from oqlos.api import hardware_actuators as actuators
from oqlos.api import hardware_lung as lung
from oqlos.api.hardware_lung import command_payload
from oqlos.errors import OqlosError
from oqlos.errors.fastapi_integration import install_oqlos_error_handler


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
    assert "/api/v1/hardware/valve/{valve_id}" in paths
    assert "/api/v1/hardware/pump" in paths
    assert "/api/v1/hardware/lung" in paths
    assert "/api/v1/hardware/artificial-lung/status" in paths


def test_command_payload_requires_command_name():
    with pytest.raises(OqlosError) as exc:
        command_payload({})
    assert exc.value.status_code == 422
    assert exc.value.public_code == "C2004-DATA-0002"


def test_artificial_lung_invalid_args_are_problem_details_before_hardware():
    app = FastAPI()
    install_oqlos_error_handler(app)
    app.include_router(lung.router, prefix="/api/v1/hardware")

    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/hardware/artificial-lung/command",
        json={"command": "set_lpm", "args": "password=hunter2"},
        headers={"X-Correlation-ID": "cor-lung-validation"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "C2004-DATA-0002"
    assert body["correlation_id"] == "cor-lung-validation"
    assert body["component"] == "artificial-lung"
    assert body["stage"] == "command.validate"
    assert body["metadata"]["context"]["field"] == "args"
    assert "hunter2" not in response.text


def test_set_pump_raises_typed_error_when_dri0050_unavailable(monkeypatch):
    class _Gateway:
        async def set_pump(self, power_pct: float):
            return {"success": False, "error": "Motor plugin not available"}

    monkeypatch.setattr(actuators, "get_hardware_gateway", lambda: _Gateway())

    with pytest.raises(OqlosError) as caught:
        asyncio.run(actuators.set_pump(12.5))
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "hw_dri0050_sidecar_unreachable"


def test_set_valve_raises_typed_error_when_modbus_io_unavailable(monkeypatch):
    class _Gateway:
        async def set_valve(self, valve_id: str, value: bool):
            return False

    monkeypatch.setattr(actuators, "get_hardware_gateway", lambda: _Gateway())

    with pytest.raises(OqlosError) as caught:
        asyncio.run(actuators.set_valve("DO1", True))
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "hw_modbus_no_response"


def test_lung_stop_raises_typed_error_when_tic249_unavailable(monkeypatch):
    class _Gateway:
        async def stop_lung(self):
            return False

    monkeypatch.setattr(lung, "get_hardware_gateway", lambda: _Gateway())

    with pytest.raises(OqlosError) as caught:
        asyncio.run(lung.stop_lung())
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "hw_tic249_sidecar_unreachable"
