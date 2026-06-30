"""Regression tests for extracted HUI hardware routes."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from oqlos.api import hardware as hw
from oqlos.api import hardware_hui as hui
from oqlos.api.hardware_gateway import set_hardware_gateway


def test_hardware_router_includes_hui_paths():
    paths = {route.path for route in hw.router.routes}
    assert "/api/v1/hardware/hui/actions" in paths
    assert "/api/v1/hardware/hui/al/start" in paths


def test_raise_if_hui_failed_raises_on_error_payload():
    with pytest.raises(HTTPException) as exc:
        hui.raise_if_hui_failed({"ok": False, "error": "boom"})
    assert exc.value.status_code == 400


class _FakeGateway:
  async def hold(self, key: str):
      return {"ok": True, "key": key}


def test_hui_hold_start_uses_gateway(monkeypatch):
    set_hardware_gateway(_FakeGateway())

    async def _fake_start(gw, key):
        return {"ok": True, "key": key}

    monkeypatch.setattr(hui, "start_hui_hold", _fake_start)

    payload = asyncio.run(hui.hui_hold_start("head-inflate"))

    assert payload["ok"] is True
    assert payload["key"] == "head-inflate"
