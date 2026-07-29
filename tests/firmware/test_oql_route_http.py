"""HTTP semantics for POST /api/v1/oql/execute (controller injected)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oqlos.api.oql_mqtt import router, set_oql_controller
from oqlos.errors.c2004_catalog_generated import CATALOG
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

    async def manage(self, verb, args=None, *, timeout=None, correlation_id=None):
        self.manage_calls.append(
            {
                "verb": verb,
                "args": args,
                "timeout": timeout,
                "correlation_id": correlation_id,
            }
        )
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
            headers={"X-Correlation-ID": "cor-http-execute"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["node_id"] == "pi-hw"
        assert body["result"]["passed"] == 1
        assert body["correlation_id"] == "cor-http-execute"
        assert resp.headers["x-correlation-id"] == "cor-http-execute"
        # timeout_ms is converted to seconds for the controller.
        assert fake.calls[0]["timeout"] == pytest.approx(3.0)
        assert fake.calls[0]["oql"] == "SET 'VALVE-NC' 'open'"
        assert fake.calls[0]["skip_waits"] is False
        assert fake.calls[0]["correlation_id"] == "cor-http-execute"
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


def test_execute_maps_remote_timeout_to_problem_details(client):
    fake = _FakeController(
        OqlResponse(
            "c1",
            ok=False,
            result=None,
            error="secret broker detail must not escape",
            node_id="pi-hw",
            error_code="C2004-NET-0003",
            stage="mqtt.response",
        )
    )
    set_oql_controller(fake)
    try:
        resp = client.post(
            "/api/v1/oql/execute",
            json={"oql": "SET 'VALVE-NC' 'open'"},
            headers={"X-Correlation-ID": "cor-http-timeout"},
        )
        assert resp.status_code == 504
        assert resp.headers["content-type"].startswith("application/problem+json")
        body = resp.json()
        assert body["ok"] is False
        assert body["code"] == "C2004-NET-0003"
        assert body["error"] == CATALOG["C2004-NET-0003"].message
        assert body["correlation_id"] == "cor-http-timeout"
        assert resp.headers["x-correlation-id"] == "cor-http-timeout"
        assert body["component"] == "oql-mqtt-agent"
        assert body["stage"] == "mqtt.response"
        assert body["metadata"]["context"]["operation_id"] == "oql.execute"
        assert body["metadata"]["context"]["problem_source"] == "upstream"
        assert body["metadata"]["context"]["upstream_target"] == "mqtt-node://pi-hw/oql"
        assert "secret broker detail" not in resp.text
        assert "traceback" not in resp.text.lower()
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
            headers={"X-Request-ID": "cor-http-manage"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["result"]["count"] == 6
        call = fake.manage_calls[0]
        assert call["verb"] == "usb-reset"
        assert call["args"] == {"vendor_id": "1ffb"}
        assert call["timeout"] == pytest.approx(5.0)
        assert call["correlation_id"] == "cor-http-manage"
        assert body["correlation_id"] == "cor-http-manage"
        assert resp.headers["x-correlation-id"] == "cor-http-manage"
    finally:
        set_oql_controller(None)


def test_manage_maps_remote_hardware_error_without_leaking_detail(client):
    fake = _FakeController(
        OqlResponse(
            "c1",
            ok=False,
            result=None,
            error="serial password=hunter2",
            node_id="boardnet",
            error_code="C2004-HW-0012",
            component="modbus-adapter",
            stage="modbus.write",
        )
    )
    set_oql_controller(fake)
    try:
        resp = client.post("/api/v1/oql/manage", json={"verb": "health"})
        assert resp.status_code == CATALOG["C2004-HW-0012"].http_status
        body = resp.json()
        assert body["ok"] is False
        assert body["code"] == "C2004-HW-0012"
        assert body["error"] == CATALOG["C2004-HW-0012"].message
        assert body["component"] == "modbus-adapter"
        assert body["stage"] == "modbus.write"
        assert body["metadata"]["context"]["operation_id"] == "oql.manage"
        assert body["metadata"]["context"]["problem_source"] == "upstream"
        assert "hunter2" not in resp.text
    finally:
        set_oql_controller(None)


def test_websocket_returns_structured_error_when_transport_disabled(client):
    set_oql_controller(None)

    with client.websocket_connect("/api/v1/oql/ws") as websocket:
        assert websocket.receive_json() == {
            "error": "OQL MQTT transport is disabled (role=off)"
        }


def test_main_websocket_alias_has_a_bound_handler():
    from oqlos.api import main
    from oqlos.api.oql_mqtt import oql_ws

    assert main._oql_ws_handler is oql_ws
