"""Regression tests for extracted HUI hardware routes."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oqlos.api import hardware as hw
from oqlos.api import hardware_hui as hui
from oqlos.errors import OqlosError
from oqlos.errors.fastapi_integration import install_oqlos_error_handler


def test_hardware_router_includes_hui_paths():
    app = FastAPI()
    app.include_router(hw.router)
    paths = set(app.openapi()["paths"])
    assert "/api/v1/hardware/hui/actions" in paths
    assert "/api/v1/hardware/hui/al/start" in paths


def test_raise_if_hui_failed_raises_on_error_payload():
    with pytest.raises(OqlosError) as exc:
        hui.raise_if_hui_failed({"ok": False, "error": "boom"})
    assert exc.value.status_code == 422
    assert exc.value.public_code == "C2004-DATA-0002"


def test_raise_if_hui_failed_preserves_hardware_unavailable_status():
    with pytest.raises(OqlosError) as exc:
        hui.raise_if_hui_failed(
            {
                "ok": False,
                "error": "Required hardware unavailable: modbus-io",
                "status_code": 503,
            }
        )
    assert exc.value.status_code == 503
    assert exc.value.public_code == "C2004-HW-0012"


def test_raise_if_hui_failed_rejects_invalid_status_metadata_safely():
    with pytest.raises(OqlosError) as exc:
        hui.raise_if_hui_failed(
            {"ok": False, "status_code": "password=hunter2", "error": "failed"}
        )

    assert exc.value.status_code == 422
    assert exc.value.public_code == "C2004-DATA-0002"


class _FakeGateway:
  async def hold(self, key: str):
      return {"ok": True, "key": key}


def test_hui_hold_start_uses_gateway(monkeypatch):
    monkeypatch.setattr(hui, "get_hardware_gateway", lambda: _FakeGateway())

    async def _fake_start(gw, key):
        return {"ok": True, "key": key}

    monkeypatch.setattr(hui, "start_hui_hold", _fake_start)

    payload = asyncio.run(hui.hui_hold_start("head-inflate"))

    assert payload["ok"] is True
    assert payload["key"] == "head-inflate"


def test_hui_al_stop_maps_safe_state_failure_to_service_unavailable(monkeypatch):
    monkeypatch.setattr(hui, "get_hardware_gateway", lambda: _FakeGateway())

    async def _fake_stop(gw):
        return {
            "ok": False,
            "error": "Required hardware unavailable while stopping artificial lung",
            "error_code": "C2004-HW-0012",
            "status_code": 503,
            "safe_to_retry": True,
        }

    monkeypatch.setattr(hui, "stop_hui_artificial_lung", _fake_stop)

    with pytest.raises(OqlosError) as exc:
        asyncio.run(hui.hui_al_stop())

    assert exc.value.status_code == 503
    assert exc.value.public_code == "C2004-HW-0012"


def test_hui_failure_http_contract_does_not_leak_action_error(monkeypatch):
    monkeypatch.setattr(hui, "get_hardware_gateway", lambda: _FakeGateway())

    async def _fake_stop(_gateway):
        return {
            "ok": False,
            "error": "password=hunter2",
            "error_code": "C2004-HW-0012",
            "status_code": 503,
        }

    monkeypatch.setattr(hui, "stop_hui_artificial_lung", _fake_stop)
    app = FastAPI()
    install_oqlos_error_handler(app)
    app.include_router(hui.router, prefix="/api/v1/hardware")

    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/hardware/hui/al/stop",
        headers={"X-Correlation-ID": "cor-hui-failure"},
    )

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "C2004-HW-0012"
    assert body["correlation_id"] == "cor-hui-failure"
    assert body["component"] == "hardware-hui"
    assert body["stage"] == "action.execute"
    assert "hunter2" not in response.text
