"""Regression tests for scenario editor file CRUD API."""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from oqlos.api import editor
from oqlos.api.main import app
from oqlos.api.oql_mqtt import set_oql_controller
from oqlos.hardware.transport.mqtt_protocol import OqlResponse


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
    resp = client.delete(
        "/api/v1/editor/file/missing.oql",
        headers={"X-Correlation-ID": "cor-editor-missing"},
    )
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["code"] == "C2004-DATA-0001"
    assert body["correlation_id"] == "cor-editor-missing"
    assert body["stage"] == "file.lookup"
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "api_editor_file_not_found"
    )


@pytest.mark.parametrize(
    ("target", "method", "operation_id"),
    [
        ("read_file", "GET", "editor.file.read"),
        ("delete_file", "DELETE", "editor.file.delete"),
    ],
)
def test_editor_missing_file_is_safe_typed_not_found(
    monkeypatch, target: str, method: str, operation_id: str
) -> None:
    def _raise_missing(*_args, **_kwargs):
        raise FileNotFoundError("password=hunter2 missing path")

    monkeypatch.setattr(editor, target, _raise_missing)

    response = TestClient(app, raise_server_exceptions=False).request(
        method,
        "/api/v1/editor/file/password=hunter2.oql",
        headers={"X-Correlation-ID": "cor-editor-missing-contract"},
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "C2004-DATA-0001"
    assert body["correlation_id"] == "cor-editor-missing-contract"
    assert body["component"] == "scenario-editor"
    assert body["stage"] == "file.lookup"
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "api_editor_file_not_found"
    )
    assert body["metadata"]["context"]["operation_id"] == operation_id
    assert "hunter2" not in response.text


def test_editor_execute_missing_file_is_safe_typed_not_found(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(editor, "SCENARIOS_DIR", tmp_path)

    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/editor/execute",
        json={"scenario_file": "password=hunter2.oql"},
        headers={"X-Correlation-ID": "cor-editor-execute-missing"},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "C2004-DATA-0001"
    assert body["correlation_id"] == "cor-editor-execute-missing"
    assert body["stage"] == "file.lookup"
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "api_editor_file_not_found"
    )
    assert body["metadata"]["context"]["operation_id"] == (
        "editor.scenario.execute"
    )
    assert "hunter2" not in response.text


@pytest.mark.parametrize(
    ("target", "method", "operation_id"),
    [
        ("read_file", "GET", "editor.file.read"),
        ("delete_file", "DELETE", "editor.file.delete"),
    ],
)
def test_editor_directory_target_is_safe_typed_validation_error(
    monkeypatch, target: str, method: str, operation_id: str
) -> None:
    def _raise_directory(*_args, **_kwargs):
        raise IsADirectoryError("password=hunter2 directory path")

    monkeypatch.setattr(editor, target, _raise_directory)

    response = TestClient(app, raise_server_exceptions=False).request(
        method,
        "/api/v1/editor/file/password=hunter2",
        headers={"X-Correlation-ID": "cor-editor-directory"},
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "C2004-DATA-0002"
    assert body["correlation_id"] == "cor-editor-directory"
    assert body["component"] == "scenario-editor"
    assert body["stage"] == "target.validate"
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "api_editor_target_invalid"
    )
    assert body["metadata"]["context"]["operation_id"] == operation_id
    assert "hunter2" not in response.text


@pytest.mark.parametrize(
    ("target", "method", "path", "payload"),
    [
        ("iter_entries", "GET", "/api/v1/editor/files", None),
        (
            "read_file",
            "GET",
            "/api/v1/editor/file/password=hunter2.oql",
            None,
        ),
        (
            "write_file",
            "POST",
            "/api/v1/editor/file/password=hunter2.oql",
            {"path": "password=hunter2.oql", "content": "secret"},
        ),
        (
            "delete_file",
            "DELETE",
            "/api/v1/editor/file/password=hunter2.oql",
            None,
        ),
        (
            "_ensure_safe_path",
            "POST",
            "/api/v1/editor/execute",
            {"scenario_file": "password=hunter2.oql"},
        ),
    ],
)
def test_editor_unexpected_failure_uses_sanitized_api_boundary(
    monkeypatch, target: str, method: str, path: str, payload
) -> None:
    def _raise_unexpected(*_args, **_kwargs):
        raise RuntimeError("password=hunter2 internal filesystem failure")

    monkeypatch.setattr(editor, target, _raise_unexpected)

    response = TestClient(app, raise_server_exceptions=False).request(
        method,
        path,
        json=payload,
        headers={"X-Correlation-ID": "cor-editor-unexpected"},
    )

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "C2004-SYS-0000"
    assert body["correlation_id"] == "cor-editor-unexpected"
    assert body["stage"] == "api.error"
    assert "hunter2" not in response.text
    assert "internal filesystem failure" not in response.text


@pytest.mark.parametrize(
    ("target", "method", "path", "payload", "operation_id"),
    [
        (
            "read_file",
            "GET",
            "/api/v1/editor/file/password=hunter2.oql",
            None,
            "editor.file.read",
        ),
        (
            "write_file",
            "POST",
            "/api/v1/editor/file/password=hunter2.oql",
            {"path": "password=hunter2.oql", "content": "secret"},
            "editor.file.write",
        ),
        (
            "delete_file",
            "DELETE",
            "/api/v1/editor/file/password=hunter2.oql",
            None,
            "editor.file.delete",
        ),
        (
            "_ensure_safe_path",
            "POST",
            "/api/v1/editor/execute",
            {"scenario_file": "password=hunter2.oql"},
            "editor.scenario.execute",
        ),
    ],
)
def test_editor_path_escape_is_safe_typed_auth_error(
    monkeypatch, target: str, method: str, path: str, payload, operation_id: str
) -> None:
    def _raise_path_escape(*_args, **_kwargs):
        raise editor.PathEscapeError("password=hunter2 filesystem root")

    monkeypatch.setattr(editor, target, _raise_path_escape)

    response = TestClient(app, raise_server_exceptions=False).request(
        method,
        path,
        json=payload,
        headers={"X-Correlation-ID": "cor-editor-path"},
    )

    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "C2004-AUTH-0002"
    assert body["correlation_id"] == "cor-editor-path"
    assert body["component"] == "scenario-editor"
    assert body["stage"] == "path.authorize"
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "api_editor_path_forbidden"
    )
    assert body["metadata"]["context"]["operation_id"] == operation_id
    assert "hunter2" not in response.text
    assert "filesystem root" not in response.text


def test_panel_and_rtc_routes_are_reachable():
    client = TestClient(app)
    panel = client.get("/ui/panel", follow_redirects=False)
    assert panel.status_code == 200

    rtc = client.get("/rtc", follow_redirects=False)
    assert rtc.status_code in {302, 307}
    assert rtc.headers["location"].endswith("/ui/hardware-rtc")


class _FakeEditorController:
    def __init__(self, response: OqlResponse):
        self.response = response
        self.calls: list[dict] = []

    async def execute(self, oql, **kwargs):
        self.calls.append({"oql": oql, **kwargs})
        return self.response


def test_editor_remote_failure_is_problem_details_not_http_200(tmp_path, monkeypatch):
    monkeypatch.setattr("oqlos.api.editor.SCENARIOS_DIR", tmp_path)
    scenario = tmp_path / "remote.oql"
    scenario.write_text("VERSION: 4\nSCENARIO: remote\n", encoding="utf-8")
    controller = _FakeEditorController(
        OqlResponse(
            "remote-correlation",
            ok=False,
            error="password=hunter2",
            node_id="pi-hw",
            error_code="C2004-NET-0003",
            stage="mqtt.response",
        )
    )
    set_oql_controller(controller)
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/v1/editor/execute",
            json={"scenario_file": "remote.oql", "mode": "execute"},
            headers={"X-Correlation-ID": "cor-editor-remote"},
        )
    finally:
        set_oql_controller(None)

    assert response.status_code == 504
    body = response.json()
    assert body["code"] == "C2004-NET-0003"
    assert body["correlation_id"] == "cor-editor-remote"
    assert body["metadata"]["context"]["operation_id"] == (
        "editor.execute-scenario"
    )
    assert controller.calls[0]["correlation_id"] == "cor-editor-remote"
    assert "hunter2" not in response.text


def test_editor_remote_success_returns_correlation_id(tmp_path, monkeypatch):
    monkeypatch.setattr("oqlos.api.editor.SCENARIOS_DIR", tmp_path)
    scenario = tmp_path / "remote.oql"
    scenario.write_text("VERSION: 4\nSCENARIO: remote\n", encoding="utf-8")
    controller = _FakeEditorController(
        OqlResponse(
            "remote-correlation",
            ok=True,
            result={"ok": True, "total": 1, "steps": [{}]},
            node_id="pi-hw",
        )
    )
    set_oql_controller(controller)
    try:
        response = TestClient(app).post(
            "/api/v1/editor/execute",
            json={"scenario_file": "remote.oql", "mode": "execute"},
            headers={"X-Request-ID": "cor-editor-success"},
        )
    finally:
        set_oql_controller(None)

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["correlation_id"] == "cor-editor-success"
    assert response.headers["x-correlation-id"] == "cor-editor-success"
