"""HTTP semantics for POST /api/v1/oql/execute (controller injected)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oqlos.api.oql_mqtt import router, set_oql_controller
from oqlos.errors.fastapi_integration import install_oqlos_error_handler
from oqlos.hardware.transport.mqtt_oql_bridge import OqlResponse


class _FakeController:
    def __init__(self, response: OqlResponse):
        self._response = response
        self.calls: list[dict] = []
        self.manage_calls: list[dict] = []

    async def execute(self, oql, **kwargs):
        self.calls.append({"oql": oql, **kwargs})
        return self._response

    async def manage(self, verb, args=None, *, timeout=None):
        self.manage_calls.append({"verb": verb, "args": args, "timeout": timeout})
        return self._response


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    install_oqlos_error_handler(app)
    return TestClient(app)


def test_execute_returns_503_when_transport_disabled(client):
    set_oql_controller(None)
    resp = client.post("/api/v1/oql/execute", json={"oql": "SET 'VALVE-NC' 'open'"})
    assert resp.status_code == 503
    assert resp.json()["code"] == "C2004-HW-0012"
    assert resp.json()["metadata"]["diagnostics"]["issue_code"] == "api_oql_transport_disabled"


def test_execute_dispatches_to_controller(client):
    fake = _FakeController(
        OqlResponse("c1", ok=True, result={"ok": True, "passed": 1}, error=None, node_id="pi-hw")
    )
    set_oql_controller(fake)
    try:
        resp = client.post(
            "/api/v1/oql/execute",
            json={"oql": "SET 'VALVE-NC' 'open'", "mode": "execute", "timeout_ms": 3000},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["node_id"] == "pi-hw"
        assert body["result"]["passed"] == 1
        # timeout_ms is converted to seconds for the controller.
        assert fake.calls[0]["timeout"] == pytest.approx(3.0)
        assert fake.calls[0]["oql"] == "SET 'VALVE-NC' 'open'"
        assert fake.calls[0]["skip_waits"] is False
    finally:
        set_oql_controller(None)


def test_execute_accepts_explicit_skip_waits(client):
    fake = _FakeController(
        OqlResponse("c1", ok=True, result={"ok": True}, error=None, node_id="pi-hw")
    )
    set_oql_controller(fake)
    try:
        resp = client.post(
            "/api/v1/oql/execute",
            json={"oql": "SET WAIT '1 s'", "skip_waits": True},
        )
        assert resp.status_code == 200
        assert fake.calls[0]["skip_waits"] is True
    finally:
        set_oql_controller(None)


def test_execute_surfaces_remote_error_as_ok_false(client):
    fake = _FakeController(
        OqlResponse("c1", ok=False, result=None, error="remote OQL execution timed out", node_id="pi-hw")
    )
    set_oql_controller(fake)
    try:
        resp = client.post("/api/v1/oql/execute", json={"oql": "SET 'VALVE-NC' 'open'"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert "timed out" in body["error"]
    finally:
        set_oql_controller(None)


def test_manage_returns_503_when_transport_disabled(client):
    set_oql_controller(None)
    resp = client.post("/api/v1/oql/manage", json={"verb": "usb-list"})
    assert resp.status_code == 503
    assert resp.json()["code"] == "C2004-HW-0012"


def test_manage_dispatches_verb_and_args(client):
    fake = _FakeController(
        OqlResponse("c1", ok=True, result={"count": 6, "devices": []}, error=None, node_id="boardnet")
    )
    set_oql_controller(fake)
    try:
        resp = client.post(
            "/api/v1/oql/manage",
            json={"verb": "usb-reset", "args": {"vendor_id": "1ffb"}, "timeout_ms": 5000},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["result"]["count"] == 6
        call = fake.manage_calls[0]
        assert call["verb"] == "usb-reset"
        assert call["args"] == {"vendor_id": "1ffb"}
        assert call["timeout"] == pytest.approx(5.0)
    finally:
        set_oql_controller(None)


def test_manage_surfaces_remote_error(client):
    fake = _FakeController(
        OqlResponse("c1", ok=False, result=None, error="remote OQL execution timed out", node_id="boardnet")
    )
    set_oql_controller(fake)
    try:
        resp = client.post("/api/v1/oql/manage", json={"verb": "health"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert "timed out" in body["error"]
    finally:
        set_oql_controller(None)
