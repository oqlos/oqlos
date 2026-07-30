"""Contract tests for the persistent UI preferences boundary."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
import pytest

from oqlos.api import ui_prefs_routes
from oqlos.api.main import app
from oqlos.api.ui_prefs_store import UiPrefsStore


def _assert_safe_store_problem(response, *, stage: str, operation_id: str) -> None:
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "C2004-NET-0002"
    assert body["correlation_id"] == "cor-ui-prefs"
    assert body["component"] == "ui-prefs-store"
    assert body["stage"] == stage
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "api_ui_prefs_store_unavailable"
    )
    assert body["metadata"]["context"] == {
        "architecture": "SOA",
        "layer": "oqlos",
        "component": "ui-prefs-store",
        "stage": stage,
        "problem_source": "storage",
        "operation_id": operation_id,
        "upstream_target": "file-store://ui-preferences",
    }
    assert "hunter2" not in response.text
    assert "/srv/private" not in response.text


def test_store_does_not_hide_malformed_json(tmp_path) -> None:
    path = tmp_path / "ui-prefs.json"
    path.write_text('{"prefs": password=hunter2}', encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        UiPrefsStore(path).get()


def test_store_merge_loads_existing_prefs_before_persisting(tmp_path) -> None:
    path = tmp_path / "ui-prefs.json"
    path.write_text('{"prefs": {"sidebar": "collapsed"}}', encoding="utf-8")

    result = UiPrefsStore(path).merge({"panel": "pinned"})

    assert result == {"sidebar": "collapsed", "panel": "pinned"}
    assert json.loads(path.read_text(encoding="utf-8"))["prefs"] == result


def test_get_ui_prefs_sanitizes_store_read_failure(monkeypatch) -> None:
    class _FailingStore:
        file_path = "/srv/private/password=hunter2/ui-prefs.yaml"

        def get(self):
            raise OSError("cannot read /srv/private password=hunter2")

    monkeypatch.setattr(ui_prefs_routes, "ui_prefs_store", _FailingStore())

    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/v3/ui/prefs",
        headers={"X-Correlation-ID": "cor-ui-prefs"},
    )

    _assert_safe_store_problem(
        response,
        stage="preferences.load",
        operation_id="ui.preferences.read",
    )


def test_put_ui_prefs_sanitizes_store_write_failure(monkeypatch) -> None:
    class _FailingStore:
        file_path = "/srv/private/password=hunter2/ui-prefs.yaml"

        def merge(self, _prefs, *, persist: bool):
            assert persist is True
            raise OSError("cannot write /srv/private password=hunter2")

    monkeypatch.setattr(ui_prefs_routes, "ui_prefs_store", _FailingStore())

    response = TestClient(app, raise_server_exceptions=False).put(
        "/api/v3/ui/prefs",
        json={"prefs": {"secret": "hunter2"}, "persist": True, "merge": True},
        headers={"X-Correlation-ID": "cor-ui-prefs"},
    )

    _assert_safe_store_problem(
        response,
        stage="preferences.persist",
        operation_id="ui.preferences.write",
    )
