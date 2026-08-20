"""Regression tests for live HUI OQL publication on BoardNet."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from oqlos.api.main import app
from oqlos.hardware.hui_profiles_oql import clear_oql_hui_profiles_cache


def _source(*, speed: int = 7_000, maximum: int = 12_000) -> str:
    return f"""VERSION: 6
SCENARIO: Test HUI profile
CONFIG:
  SET 'hui.lung.stroke_steps' '9000'
  SET 'hui.lung.speed_steps_per_second' '{speed}'
  SET 'hui.lung.max_steps_per_second' '{maximum}'
  SET 'hui.lung.ramp_seconds' '0'
  SET 'hui.lung.pause' '0'
  SET 'hui.lung.cycles' '10'
  SET 'hui.lung.stop_at_limit' 'false'
"""


def test_system_role_publishes_profile_for_next_start(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "hui-profiles.oql"
    target.write_text(_source(speed=3_000), encoding="utf-8")
    monkeypatch.setenv("OQLOS_HUI_PROFILES_OQL", str(target))
    clear_oql_hui_profiles_cache()

    response = TestClient(app).put(
        "/api/v1/hardware/hui/profile/source",
        headers={"X-Connect-Role": "system"},
        json={"content": _source()},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["applied"] is True
    assert payload["applies_on"] == "next-start"
    assert payload["requires_service_restart"] is False
    assert payload["effective"]["speed"] == 70_000_000
    assert payload["effective"]["pause"] == 0.0
    assert target.read_text(encoding="utf-8") == _source()
    clear_oql_hui_profiles_cache()


def test_profile_publication_rejects_speed_above_physical_limit(
    tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "hui-profiles.oql"
    original = _source()
    target.write_text(original, encoding="utf-8")
    monkeypatch.setenv("OQLOS_HUI_PROFILES_OQL", str(target))
    clear_oql_hui_profiles_cache()

    response = TestClient(app, raise_server_exceptions=False).put(
        "/api/v1/hardware/hui/profile/source",
        headers={"X-Connect-Role": "system"},
        json={"content": _source(speed=12_001, maximum=12_001)},
    )

    assert response.status_code == 422
    assert target.read_text(encoding="utf-8") == original
    clear_oql_hui_profiles_cache()


def test_profile_publication_requires_system_role(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "hui-profiles.oql"
    target.write_text(_source(), encoding="utf-8")
    monkeypatch.setenv("OQLOS_HUI_PROFILES_OQL", str(target))

    response = TestClient(app, raise_server_exceptions=False).put(
        "/api/v1/hardware/hui/profile/source",
        headers={"X-Connect-Role": "operator"},
        json={"content": _source(speed=5_000)},
    )

    assert response.status_code == 403
    assert target.read_text(encoding="utf-8") == _source()
