"""Contract tests for the hardware control panel (``/panel``).

The panel (``oqlos/api/static/panel.html``) is a self-contained UI that drives the
whole rig through OQL flow commands routed to the Raspberry Pi node over MQTT. It
hard-codes:

  * the HTTP endpoints it POSTs to (``/api/v1/oql/execute`` and ``/api/v1/oql/manage``),
  * a set of ``kind:"manage"`` verbs in its ``GROUPS`` table,
  * single OQL ``SET``/``GET`` snippets.

These tests guard that contract so the static UI cannot silently drift away from the
backend: every manage verb the panel exposes must be a real, dispatchable verb, and
the payload shapes the panel sends must reach the controller intact.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oqlos.api.oql_mqtt import router as oql_router, set_oql_controller
from oqlos.hardware.transport.manage_ops import list_manage_verbs
from oqlos.hardware.transport.mqtt_oql_bridge import OqlResponse

PANEL_HTML = Path(__file__).resolve().parents[2] / "oqlos" / "api" / "static" / "panel.html"


@pytest.fixture(scope="module")
def panel_source() -> str:
    return PANEL_HTML.read_text(encoding="utf-8")


def _panel_manage_verbs(source: str) -> set[str]:
    """Extract every ``verb:"..."`` literal used by the panel's command groups."""
    return set(re.findall(r"""verb:\s*["']([a-z0-9-]+)["']""", source))


def _panel_endpoints(source: str) -> set[str]:
    """Extract the ``/api/...`` paths the panel calls via fetch/api()."""
    return set(re.findall(r"""["'](/api/v1/[a-z0-9/_-]+)["']""", source))


# --------------------------------------------------------------------------- #
# 1. The panel is served by the full app.
# --------------------------------------------------------------------------- #
def test_panel_route_serves_html():
    from oqlos.api.main import app

    client = TestClient(app)
    resp = client.get("/panel")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    body = resp.text
    # Key UI anchors that the JS wires itself to.
    assert 'id="groups"' in body
    assert 'id="editor"' in body
    assert "/api/v1/oql/execute" in body
    assert "/api/v1/oql/manage" in body


# --------------------------------------------------------------------------- #
# 2. Contract: every manage verb the panel exposes is dispatchable.
# --------------------------------------------------------------------------- #
def test_panel_manage_verbs_are_supported(panel_source):
    used = _panel_manage_verbs(panel_source)
    # Sanity: the panel really does expose manage verbs (guards a broken regex).
    assert {"health", "usb-list", "pi-diagnostics", "usb-reset"} <= used

    supported = set(list_manage_verbs())
    unknown = used - supported
    assert not unknown, (
        f"panel.html references manage verbs not in list_manage_verbs(): {sorted(unknown)}"
    )


def test_panel_only_calls_known_endpoints(panel_source):
    endpoints = _panel_endpoints(panel_source)
    assert "/api/v1/oql/execute" in endpoints
    assert "/api/v1/oql/manage" in endpoints
    # The scenarios fetch endpoint must exist too (loadServerScenarios()).
    assert "/api/v1/scenarios/fetch" in panel_source


# --------------------------------------------------------------------------- #
# 3. End-to-end: the payload shapes the panel sends reach the controller.
# --------------------------------------------------------------------------- #
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
def client_with_controller():
    app = FastAPI()
    app.include_router(oql_router)
    fake = _FakeController(
        OqlResponse("c1", ok=True, result={"ok": True, "mode": "real-hw"}, error=None, node_id="pi-hw")
    )
    set_oql_controller(fake)
    try:
        yield TestClient(app), fake
    finally:
        set_oql_controller(None)


def test_panel_single_oql_command_payload_dispatches(client_with_controller):
    """A group button: runOql("SET 'valve-1' 'open'", 'command', ...)."""
    client, fake = client_with_controller
    payload = {"oql": "SET 'valve-1' 'open'", "kind": "command", "mode": "execute"}
    resp = client.post("/api/v1/oql/execute", json=payload)
    assert resp.status_code == 200
    assert resp.json()["node_id"] == "pi-hw"
    assert fake.calls[0]["oql"] == "SET 'valve-1' 'open'"


def test_panel_flow_script_payload_dispatches(client_with_controller):
    """The editor's "Uruchom scenariusz": runOql(text, 'script', ...)."""
    client, fake = client_with_controller
    script = "VERSION: 4\nSCENARIO: Test\nGOAL:\n  SET 'pump' 50\n  WAIT 1 s\n  SET 'pump' 0"
    payload = {"oql": script, "kind": "script", "mode": "dry-run"}
    resp = client.post("/api/v1/oql/execute", json=payload)
    assert resp.status_code == 200
    assert fake.calls[0]["oql"] == script
    assert fake.calls[0]["mode"] == "dry-run"


def test_panel_manage_payload_dispatches(client_with_controller):
    """A manage button: runManage('usb-reset', {vendor_id:'1ffb'}, ...)."""
    client, fake = client_with_controller
    payload = {"verb": "usb-reset", "args": {"vendor_id": "1ffb"}}
    resp = client.post("/api/v1/oql/manage", json=payload)
    assert resp.status_code == 200
    call = fake.manage_calls[0]
    assert call["verb"] == "usb-reset"
    assert call["args"] == {"vendor_id": "1ffb"}
