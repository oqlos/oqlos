from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from oqlos.api import hardware_v3
from oqlos.api import _hw3_models


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(hardware_v3.router)
    return TestClient(app)


def test_hardware_v3_cqrs_events_record_diagnostic_failure(monkeypatch):
    client = _client()
    client.post("/api/v3/hardware/cqrs/events/clear", json={"truncate_persistent": False})

    async def _fake_run_manage_verb(verb, args=None):
        raise RuntimeError(f"not available: {verb}")

    monkeypatch.setattr(_hw3_models, "run_manage_verb", _fake_run_manage_verb)
    response = client.post(
        "/api/v3/hardware/diagnostic-command",
        json={"peripheral_id": "motor-dri0050", "command": "pump_off", "args": {}},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is False

    events = client.get("/api/v3/hardware/cqrs/events?limit=5")
    assert events.status_code == 200
    payload = events.json()
    assert payload["count"] == 1
    event_payload = payload["events"][0]["payload"]
    assert event_payload["peripheral_id"] == "motor-dri0050"
    assert event_payload["command_name"] == "pump_off"


def test_hardware_ui_aliases_and_status_page_are_served():
    from oqlos.api.main import app

    client = TestClient(app)
    status = client.get("/hardware-status", follow_redirects=False)
    assert status.status_code in {302, 307}
    assert status.headers["location"] == "/ui/status"

    ui_status = client.get("/ui/status")
    assert ui_status.status_code == 200
    assert "text/html" in ui_status.headers["content-type"]

    legacy_ui_status = client.get("/ui/hardware-status", follow_redirects=False)
    assert legacy_ui_status.status_code in {302, 307}
    assert legacy_ui_status.headers["location"] == "/ui/status"

    demo = client.get("/hardware-demo?lang=pl", follow_redirects=False)
    assert demo.status_code in {302, 307}
    assert demo.headers["location"] == "/ui/motor-services?lang=pl"

    restart = client.get("/hardware-restart?lang=pl", follow_redirects=False)
    assert restart.status_code in {302, 307}
    assert restart.headers["location"] == "/ui/hardware-modbus?lang=pl"

    modbus = client.get("/hardware-modbus?lang=pl", follow_redirects=False)
    assert modbus.status_code in {302, 307}
    assert modbus.headers["location"] == "/ui/hardware-modbus?lang=pl"

    rtc = client.get("/hardware-rtc?lang=pl", follow_redirects=False)
    assert rtc.status_code in {302, 307}
    assert rtc.headers["location"] == "/ui/hardware-rtc?lang=pl"

    editor = client.get("/map-editor", follow_redirects=False)
    assert editor.status_code == 404

    scenario_files = client.get("/scenario-files?scenario=demo.oql", follow_redirects=False)
    assert scenario_files.status_code in {302, 307}
    assert scenario_files.headers["location"] == "/ui/scenario-files?scenario=demo.oql"

    func_editor = client.get("/func-editor", follow_redirects=False)
    assert func_editor.status_code in {302, 307}
    assert func_editor.headers["location"] == "/ui/func-editor"

    editor = client.get("/editor?scenario=demo.oql", follow_redirects=False)
    assert editor.status_code in {302, 307}
    assert editor.headers["location"] == "/ui/scenario-files?scenario=demo.oql"

    navigation = client.get("/navigation", follow_redirects=False)
    assert navigation.status_code in {302, 307}
    assert navigation.headers["location"] == "/ui/status"

    ui_navigation = client.get("/ui/navigation", follow_redirects=False)
    assert ui_navigation.status_code in {302, 307}
    assert ui_navigation.headers["location"] == "/ui/status"


def test_navigation_index_and_short_aliases():
    from oqlos.api.main import app

    client = TestClient(app)
    response = client.get("/api/v1/navigation")
    assert response.status_code == 200
    body = response.json()
    page_paths = {item["path"] for item in body["pages"]}
    api_paths = {item["path"] for item in body["api"]}
    aliases = {item["path"]: item["target"] for item in body["aliases"]}

    assert "/ui/status" in page_paths
    assert "/ui/panel" in page_paths
    assert "/ui/hardware-rtc" in page_paths
    assert "/api/v1/oql/execute" in api_paths
    assert "/api/v1/oql/manage" in api_paths
    assert aliases["/status"] == "/ui/status"
    assert aliases["/oql"] == "/ui/panel"

    expected_redirects = {
        "/nav": "/ui/status",
        "/navigation": "/ui/status",
        "/status": "/ui/status",
        "/restart": "/ui/hardware-modbus",
        "/hardware-restart": "/ui/hardware-modbus",
        "/modbus": "/ui/hardware-modbus",
        "/hardware-rtc": "/ui/hardware-rtc",
        "/rtc": "/ui/hardware-rtc",
        "/demo": "/ui/motor-services",
        "/files": "/ui/scenario-files",
        "/functions": "/ui/func-editor",
        "/oql": "/ui/panel",
        "/oql-panel": "/ui/panel",
        "/panel": "/ui/panel",
    }
    for path, target in expected_redirects.items():
        redirected = client.get(path, follow_redirects=False)
        assert redirected.status_code in {302, 307}
        assert redirected.headers["location"] == target

    assert client.get("/map", follow_redirects=False).status_code == 404
