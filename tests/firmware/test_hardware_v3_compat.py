from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from oqlos.api import hardware_v3
from oqlos.api import _hw3_mapping, _hw3_models
from oqlos.api.hardware_mapping_store import MappingStore


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(hardware_v3.router)
    return TestClient(app)


def test_hardware_v3_mapping_round_trip(monkeypatch, tmp_path):
    store = MappingStore(tmp_path / "hardware-map.yaml")
    monkeypatch.setattr(_hw3_mapping, "mapping_store", store)
    client = _client()

    schema = client.get("/api/v3/hardware/mapping/schema")
    assert schema.status_code == 200
    assert schema.json()["contract"] == "hardware-map-v1"

    mapping = {
        "runtimeConfig": {"motor_tic249": {"max_steps_per_second": 800}},
        "objectActionMap": {"motor2": {}},
        "paramSensorMap": {},
        "actions": {},
        "funcImplementations": {},
    }
    put = client.put("/api/v3/hardware/mapping", json={"mapping": mapping, "persist": True})
    assert put.status_code == 200
    body = put.json()
    assert body["ok"] is True
    assert body["mapping"]["runtimeConfig"]["motor2"]["maxStepsPerSecond"] == 800

    get = client.get("/api/v3/hardware/mapping")
    assert get.status_code == 200
    assert get.json()["mapping"]["runtimeConfig"]["motor2"]["maxStepsPerSecond"] == 800
    assert get.json()["store_path"].endswith("hardware-map.yaml")


def test_hardware_v3_mapping_rejects_invalid_contract(monkeypatch, tmp_path):
    monkeypatch.setattr(_hw3_mapping, "mapping_store", MappingStore(tmp_path / "hardware-map.yaml"))
    client = _client()

    response = client.put(
        "/api/v3/hardware/mapping",
        json={"mapping": {"runtimeConfig": {"motor2": {"strokeSteps": 0}}}},
    )

    assert response.status_code == 400
    assert "runtimeConfig.motor2.strokeSteps must be an integer >= 1" in response.text


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
    status = client.get("/hardware-status")
    assert status.status_code == 200
    assert "OqlOS Hardware Status" in status.text
    assert "/api/v3/hardware/health" in status.text
    assert "/navigation" in status.text

    demo = client.get("/hardware-demo?lang=pl", follow_redirects=False)
    assert demo.status_code in {302, 307}
    assert demo.headers["location"] == "/ui/hardware-demo?lang=pl"

    restart = client.get("/hardware-restart", follow_redirects=False)
    assert restart.status_code in {302, 307}
    assert restart.headers["location"] == "/ui/hardware-restart"

    editor = client.get("/map-editor", follow_redirects=False)
    assert editor.status_code in {302, 307}
    assert editor.headers["location"] == "/ui/map-editor"

    scenario_files = client.get("/scenario-files?scenario=demo.oql", follow_redirects=False)
    assert scenario_files.status_code in {302, 307}
    assert scenario_files.headers["location"] == "/editor?scenario=demo.oql"

    func_editor = client.get("/func-editor", follow_redirects=False)
    assert func_editor.status_code in {302, 307}
    assert func_editor.headers["location"] == "/editor"

    navigation = client.get("/navigation")
    assert navigation.status_code == 200
    assert "OqlOS BoardNet navigation" in navigation.text
    assert "/api/v1/oql/manage" in navigation.text


def test_navigation_index_and_short_aliases():
    from oqlos.api.main import app

    client = TestClient(app)
    response = client.get("/api/v1/navigation")
    assert response.status_code == 200
    body = response.json()
    page_paths = {item["path"] for item in body["pages"]}
    api_paths = {item["path"] for item in body["api"]}
    aliases = {item["path"]: item["target"] for item in body["aliases"]}

    assert "/navigation" in page_paths
    assert "/hardware-status" in page_paths
    assert "/panel" in page_paths
    assert "/api/v1/oql/execute" in api_paths
    assert "/api/v1/oql/manage" in api_paths
    assert aliases["/status"] == "/hardware-status"
    assert aliases["/oql"] == "/panel"

    expected_redirects = {
        "/nav": "/navigation",
        "/status": "/hardware-status",
        "/restart": "/hardware-restart",
        "/demo": "/hardware-demo",
        "/map": "/map-editor",
        "/files": "/scenario-files",
        "/functions": "/func-editor",
        "/oql": "/panel",
        "/oql-panel": "/panel",
    }
    for path, target in expected_redirects.items():
        redirected = client.get(path, follow_redirects=False)
        assert redirected.status_code in {302, 307}
        assert redirected.headers["location"] == target
