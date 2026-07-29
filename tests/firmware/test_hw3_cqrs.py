"""Regression tests for hardware CQRS command validation."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oqlos.api import _hw3_cqrs as cqrs
from oqlos.api._hw3_models import CqrsCommandRequest
from oqlos.errors import OqlosError
from oqlos.errors.fastapi_integration import install_oqlos_error_handler


def test_cqrs_command_raises_typed_error_when_fields_missing(monkeypatch):
    published: list[dict] = []

    async def _publish(command, result, context=None):
        published.append({"command": command, "result": result, "context": context})

    monkeypatch.setattr(cqrs, "publish_hardware_command_event", _publish)

    with pytest.raises(OqlosError) as caught:
        asyncio.run(cqrs.hardware_cqrs_command_v3(CqrsCommandRequest(command={})))
    assert caught.value.public_code == "C2004-DATA-0002"
    assert caught.value.issue_code == "api_modbus_wizard_invalid_request"
    assert published and published[0]["result"]["ok"] is False


def test_cqrs_missing_fields_are_problem_details_not_http_200(monkeypatch):
    async def _publish(*_args, **_kwargs):
        return None

    monkeypatch.setattr(cqrs, "publish_hardware_command_event", _publish)
    app = FastAPI()
    install_oqlos_error_handler(app)
    app.include_router(cqrs.router, prefix="/api/v3/hardware")

    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/v3/hardware/cqrs/command",
        json={"command": {"token": "must-not-leak"}},
        headers={"X-Correlation-ID": "cor-cqrs-contract"},
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "C2004-DATA-0002"
    assert body["correlation_id"] == "cor-cqrs-contract"
    assert body["component"] == "hardware-cqrs"
    assert body["stage"] == "command.validate"
    assert body["metadata"]["context"]["problem_source"] == "request"
    assert body["metadata"]["context"]["missing_fields"] == [
        "peripheral_id",
        "command",
    ]
    assert "must-not-leak" not in response.text
    assert "traceback" not in response.text.lower()
