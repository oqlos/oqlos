"""Regression: diagnosis and peripherals HTTP routes."""

from __future__ import annotations


def test_hardware_diagnosis_route(monkeypatch):
  from fastapi.testclient import TestClient
  from oqlos.api.main import app

  async def _fake_identify(*, scan: str = "never"):
    return {"platform": {}, "diagnostics": {"health": {}}, "adapters": []}

  monkeypatch.setattr(
    "oqlos.api.hardware_diagnosis_routes.hardware_identify",
    _fake_identify,
  )
  monkeypatch.setattr(
    "oqlos.hardware.diagnosis.build_diagnosis_report",
    lambda _identify: type("R", (), {"devices": {}, "global_actions": [], "ok": True, "message": "ok"})(),
  )
  monkeypatch.setattr(
    "oqlos.hardware.diagnosis.report_to_dict",
    lambda _report: {"ok": True, "devices": {}, "global_actions": []},
  )

  client = TestClient(app)
  response = client.get("/api/v1/hardware/diagnosis")
  assert response.status_code == 200
  assert response.json()["ok"] is True


def test_hardware_recover_rejects_unknown_scope(monkeypatch):
  from fastapi.testclient import TestClient
  from oqlos.api.main import app

  client = TestClient(app)
  response = client.post("/api/v1/hardware/recover?scope=full")
  assert response.status_code == 400
  body = response.json()
  assert body["code"] == "C2004-DATA-0002"
  assert (
      body["metadata"]["diagnostics"]["issue_code"]
      == "api_invalid_recover_scope"
  )
  assert body["metadata"]["context"] == {"scope": "full"}
