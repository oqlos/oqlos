from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from oqlos.api import hardware_v3
from oqlos.hardware import host_power


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(hardware_v3.router)
    return TestClient(app)


def test_host_reboot_requires_confirm():
    client = _client()
    resp = client.post("/api/v3/hardware/host/reboot", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert "confirm" in body["hint"]


def test_host_reboot_refuses_in_container(monkeypatch):
    monkeypatch.setattr(host_power, "_in_container", lambda: True)
    client = _client()
    resp = client.post("/api/v3/hardware/host/reboot", json={"confirm": True})
    body = resp.json()
    assert body["ok"] is False
    assert "container" in body["error"]


def test_host_reboot_requires_passwordless_sudo(monkeypatch):
    monkeypatch.setattr(host_power, "_in_container", lambda: False)
    monkeypatch.setattr(host_power, "_sudo_available", lambda: False)
    client = _client()
    resp = client.post("/api/v3/hardware/host/reboot", json={"confirm": True})
    body = resp.json()
    assert body["ok"] is False
    assert "sudo" in body["error"]


def test_host_reboot_schedules_detached_reboot(monkeypatch):
    monkeypatch.setattr(host_power, "_in_container", lambda: False)
    monkeypatch.setattr(host_power, "_sudo_available", lambda: True)
    popen_calls = []
    monkeypatch.setattr(
        host_power.subprocess,
        "Popen",
        lambda *args, **kwargs: popen_calls.append((args, kwargs)),
    )
    client = _client()
    resp = client.post("/api/v3/hardware/host/reboot", json={"confirm": True})
    body = resp.json()
    assert body["ok"] is True
    assert body["scheduled_in_sec"] == host_power.REBOOT_DELAY_SEC
    assert len(popen_calls) == 1
    (cmd,), kwargs = popen_calls[0]
    assert "systemctl reboot" in cmd[-1]
    assert kwargs["start_new_session"] is True
