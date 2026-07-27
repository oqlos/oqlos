"""Regression tests for hardware CQRS command validation."""

from __future__ import annotations

import asyncio

import pytest

from oqlos.api import _hw3_cqrs as cqrs
from oqlos.api._hw3_models import CqrsCommandRequest
from oqlos.errors import OqlosError


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
