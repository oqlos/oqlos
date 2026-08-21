from __future__ import annotations

from fastapi.testclient import TestClient

from oqlos.api.main import app


SOURCE = """VERSION: 6
CONFIG:
  SET 'device.boardnet.motor-tic249.current_limit_ma' '1600'
  SET 'device.boardnet.motor-tic249.limit_switch_forward_pin' 'scl'
  SET 'device.boardnet.motor-tic249.limit_switch_reverse_pin' 'sda'
  SET 'device.boardnet.motor-tic249.limit_switch_pull_up' 'true'
  SET 'device.boardnet.motor-tic249.limit_switch_active_high' 'false'
"""


def test_system_role_applies_tic249_profile(monkeypatch) -> None:
    async def fake_apply(_content: str):
        return {
            "configured": {"current_limit_ma": 1600},
            "nvm": {"ok": True, "applied": False},
        }

    monkeypatch.setattr(
        "oqlos.api.hardware_tic249_profile_source.apply_tic249_profile_source",
        fake_apply,
    )
    response = TestClient(app).put(
        "/api/v1/hardware/hui/tic249/profile/source",
        headers={"X-Connect-Role": "system"},
        json={"content": SOURCE},
    )

    assert response.status_code == 200
    assert response.json()["configured"]["current_limit_ma"] == 1600
    assert response.json()["current_measurement_available"] is False


def test_tic249_profile_requires_system_role() -> None:
    response = TestClient(app, raise_server_exceptions=False).put(
        "/api/v1/hardware/hui/tic249/profile/source",
        headers={"X-Connect-Role": "operator"},
        json={"content": SOURCE},
    )
    assert response.status_code == 403
