"""Regression tests for hardware diagnostic-command error boundary."""

from __future__ import annotations

import asyncio

import pytest

from oqlos.api import _hw3_peripheral as peripheral
from oqlos.api._hw3_models import DiagnosticCommandRequest
from oqlos.errors import OqlosError


def test_diagnostic_command_raises_typed_tic249_error(monkeypatch):
    published: list[dict] = []

    async def _boom(_peripheral_id, _command, _args):
        raise RuntimeError("sidecar down")

    async def _publish(command, result, context=None):
        published.append({"command": command, "result": result, "context": context})

    monkeypatch.setattr(peripheral, "_run_diagnostic", _boom)
    monkeypatch.setattr(peripheral, "publish_hardware_command_event", _publish)

    with pytest.raises(OqlosError) as caught:
        asyncio.run(
            peripheral.hardware_diagnostic_command_v3(
                DiagnosticCommandRequest(
                    peripheral_id="tic249",
                    command="status",
                    args={},
                )
            )
        )
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "hw_tic249_sidecar_unreachable"
    assert published and published[0]["result"]["ok"] is False
