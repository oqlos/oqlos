"""Regression tests for extracted identify/health routes."""

from fastapi import FastAPI

from oqlos.api import hardware as hw


def test_hardware_router_includes_health_and_identify():
    app = FastAPI()
    app.include_router(hw.router)
    paths = set(app.openapi()["paths"])
    assert "/api/v1/hardware/health" in paths
    assert "/api/v1/hardware/identify" in paths
