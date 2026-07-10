"""Regression tests for scenario editor file CRUD API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from oqlos.api.main import app


def test_editor_file_create_read_delete_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr("oqlos.api.editor.SCENARIOS_DIR", tmp_path)
    client = TestClient(app)
    rel = "panel-crud-smoke.oql"
    content = "VERSION: 4\nSCENARIO: smoke\nGOAL:\n  SET WAIT '1 s'\n"

    created = client.post(
        f"/api/v1/editor/file/{rel}",
        json={"path": rel, "content": content},
    )
    assert created.status_code == 200
    assert created.json()["status"] == "success"

    listed = client.get("/api/v1/editor/files")
    assert listed.status_code == 200
    names = {item["name"] for item in listed.json()["files"] if not item["is_directory"]}
    assert rel in names

    read = client.get(f"/api/v1/editor/file/{rel}")
    assert read.status_code == 200
    assert read.json()["content"] == content

    deleted = client.delete(f"/api/v1/editor/file/{rel}")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "success"
    assert client.get(f"/api/v1/editor/file/{rel}").status_code == 404


def test_editor_file_delete_rejects_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr("oqlos.api.editor.SCENARIOS_DIR", tmp_path)
    client = TestClient(app)
    resp = client.delete("/api/v1/editor/file/missing.oql")
    assert resp.status_code == 404


def test_panel_and_rtc_routes_are_reachable():
    client = TestClient(app)
    panel = client.get("/ui/panel", follow_redirects=False)
    assert panel.status_code == 200

    rtc = client.get("/rtc", follow_redirects=False)
    assert rtc.status_code in {302, 307}
    assert rtc.headers["location"].endswith("/ui/hardware-rtc")
