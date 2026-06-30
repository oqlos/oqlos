"""Regression tests for extracted actuator and lung routes."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from oqlos.api import hardware as hw
from oqlos.api.hardware_lung import command_payload


def test_hardware_router_includes_actuator_and_lung_paths():
    paths = {route.path for route in hw.router.routes}
    assert "/api/v1/hardware/valve/{valve_id}" in paths
    assert "/api/v1/hardware/pump" in paths
    assert "/api/v1/hardware/lung" in paths
    assert "/api/v1/hardware/artificial-lung/status" in paths


def test_command_payload_requires_command_name():
    with pytest.raises(HTTPException) as exc:
        command_payload({})
    assert exc.value.status_code == 400
