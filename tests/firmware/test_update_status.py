"""Regression tests for OqlOS /update status."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
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

    probed_base_urls = []

    async def fake_health(base_url):
        probed_base_urls.append(base_url)
        return {"status": "ok", "components": {"oqlos": {"status": "ok"}}}

    async def fake_hw(base_url):
        probed_base_urls.append(base_url)
        return {"status": "ok", "mode": "real", "connected": 2, "failed": 0, "disabled": 1}

    monkeypatch.setattr(route_mod, "_collect_health", fake_health)
    monkeypatch.setattr(route_mod, "_collect_hardware_summary", fake_hw)

    response = client.get(
        "/api/v1/update/status", headers={"Host": "attacker.invalid:9999"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["host"] == "boardnet"
    assert payload["deploy"]["short"] == "cafebabe"
    assert payload["hardware"]["mode"] == "real"
    assert probed_base_urls == [
        f"http://127.0.0.1:{route_mod.FIRMWARE_PORT}",
        f"http://127.0.0.1:{route_mod.FIRMWARE_PORT}",
    ]


def test_update_page_served():
    response = client.get("/update")
    assert response.status_code == 200
    assert "BoardNet" in response.text
    assert "/api/v1/update/status" in response.text


def test_probe_failure_returns_stable_diagnostics_without_url_or_exception(monkeypatch):
    import oqlos.api.update_status as route_mod

    class UnavailableClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, _url):
            raise httpx.ConnectError(
                "token=probe-secret at /home/operator/private-socket"
            )

    monkeypatch.setattr(
        route_mod.httpx, "AsyncClient", lambda **_kwargs: UnavailableClient()
    )

    result = asyncio.run(
        route_mod._probe_json(
            "http://user:password@private-host/health?token=url-secret",
            component="dri0050",
        )
    )

    assert result == {
        "status": "error",
        "reason": "health-probe-unavailable",
        "diagnostics": {
            "issue_code": "hw_dri0050_sidecar_unreachable",
            "error_code": "C2004-HW-0012",
        },
    }
    serialized = json.dumps(result)
    assert "probe-secret" not in serialized
    assert "url-secret" not in serialized
    assert "private-host" not in serialized

    class MalformedJsonResponse:
        def raise_for_status(self):
            return None

        def json(self):
            raise json.JSONDecodeError("invalid response", "not-json", 0)

    class MalformedJsonClient(UnavailableClient):
        async def get(self, _url):
            return MalformedJsonResponse()

    monkeypatch.setattr(
        route_mod.httpx, "AsyncClient", lambda **_kwargs: MalformedJsonClient()
    )
    malformed = asyncio.run(
        route_mod._probe_json("http://127.0.0.1/health", component="oqlos")
    )
    assert malformed["status"] == "error"
    assert malformed["diagnostics"]["error_code"] == "C2004-HW-0011"


def test_probe_does_not_mask_programming_errors(monkeypatch):
    import oqlos.api.update_status as route_mod

    class BrokenClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, _url):
            raise AttributeError("programming defect")

    monkeypatch.setattr(route_mod.httpx, "AsyncClient", lambda **_kwargs: BrokenClient())

    with pytest.raises(AttributeError, match="programming defect"):
        asyncio.run(
            route_mod._probe_json(
                "http://127.0.0.1/health",
                component="oqlos",
            )
        )
