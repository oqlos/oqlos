"""Regression tests for OqlOS /update status."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from oqlos.api.main import app
from oqlos.services import update_status as status_mod

client = TestClient(app)


def test_update_status_endpoint(monkeypatch, tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    (tmp_path / ".deploy-commit").write_text("cafebabe\n", encoding="utf-8")

    monkeypatch.setattr(status_mod, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(status_mod, "logs_dir", lambda: logs)
    monkeypatch.setattr(
        status_mod,
        "compute_git_drift",
        lambda commit, root=None: {"status": "no-git", "head": None, "commits_behind": None},
    )

    import oqlos.api.update_status as route_mod

    async def fake_health(base_url):
        return {"status": "ok", "components": {"oqlos": {"status": "ok"}}}

    async def fake_hw(base_url):
        return {"status": "ok", "mode": "real", "connected": 2, "failed": 0, "disabled": 1}

    monkeypatch.setattr(route_mod, "_collect_health", fake_health)
    monkeypatch.setattr(route_mod, "_collect_hardware_summary", fake_hw)

    response = client.get("/api/v1/update/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["host"] == "boardnet"
    assert payload["deploy"]["short"] == "cafebabe"
    assert payload["hardware"]["mode"] == "real"


def test_update_page_served():
    response = client.get("/update")
    assert response.status_code == 200
    assert "BoardNet" in response.text
    assert "/api/v1/update/status" in response.text
