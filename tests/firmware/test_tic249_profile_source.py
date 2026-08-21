from __future__ import annotations

import json

import pytest

from oqlos.hardware import tic249_profile_source as profile_source
from oqlos.hardware.tic249_profile_source import (
    Tic249ProfileSourceError,
    Tic249ProfileUnsafeError,
    apply_tic249_profile_source,
    validate_tic249_profile_source,
)


def _source(*, current_ma: int = 1600, forward: str = "scl", reverse: str = "sda") -> str:
    return f"""VERSION: 6
CONFIG:
  SET 'device.boardnet.motor-tic249.current_limit_ma' '{current_ma}'
  SET 'device.boardnet.motor-tic249.deenergize_on_stop' 'true'
  SET 'device.boardnet.motor-tic249.deenergize_on_startup' 'true'
  SET 'device.boardnet.motor-tic249.limit_switch_forward_pin' '{forward}'
  SET 'device.boardnet.motor-tic249.limit_switch_reverse_pin' '{reverse}'
  SET 'device.boardnet.motor-tic249.limit_switch_pull_up' 'true'
  SET 'device.boardnet.motor-tic249.limit_switch_active_high' 'false'
  SET 'device.boardnet.motor-tic249.limit_reaction_delay_ms' '0'
  SET 'device.boardnet.motor-tic249.stop_at_limit' 'true'
"""


def test_profile_maps_current_and_canonical_limit_pin_directions() -> None:
    result = validate_tic249_profile_source(_source())

    assert result["current_limit_code"] == 40
    assert result["current_measurement_available"] is False
    assert result["nvm_profile"]["settings_file"] == {
        "scl_config": "pullup limit_switch_forward",
        "sda_config": "pullup limit_switch_reverse",
    }


def test_profile_rejects_noncanonical_limit_pin_directions() -> None:
    with pytest.raises(Tic249ProfileSourceError, match="SCL=forward"):
        validate_tic249_profile_source(_source(forward="sda", reverse="scl"))


def test_profile_rejects_one_pin_for_both_limits() -> None:
    with pytest.raises(Tic249ProfileSourceError, match="different pins"):
        validate_tic249_profile_source(_source(forward="scl", reverse="scl"))


def test_profile_rejects_current_above_continuous_limit() -> None:
    with pytest.raises(Tic249ProfileSourceError, match="between 0 and 1800"):
        validate_tic249_profile_source(_source(current_ma=2000))


def test_profile_rejects_unrepresentable_current() -> None:
    with pytest.raises(Tic249ProfileSourceError, match="cannot represent"):
        validate_tic249_profile_source(_source(current_ma=1800))


@pytest.mark.asyncio
async def test_apply_persists_source_and_sets_current_when_nvm_already_matches(
    tmp_path, monkeypatch
) -> None:
    source = _source()
    desired = validate_tic249_profile_source(source)["nvm_profile"]
    oql_target = tmp_path / "tic249-boardnet.oql"
    nvm_target = tmp_path / "boardnet_nvm_profile.json"
    nvm_target.write_text(json.dumps(desired), encoding="utf-8")
    monkeypatch.setenv("OQLOS_TIC249_DEVICE_OQL", str(oql_target))
    monkeypatch.setenv("OQLOS_TIC249_NVM_PROFILE", str(nvm_target))
    calls = []

    async def fake_request(method, path, *, payload=None):
        calls.append((method, path, payload))
        if path == "/api/status":
            return {
                "connected": True,
                "velocity": 0,
                "energized": False,
                "reciprocating_active": False,
            }, "http://tic"
        if path == "/api/nvm-validation":
            return {"ok": True}, "http://tic"
        return {"motor": {"current_limit_ma": 1600}}, "http://tic"

    async def must_not_apply(_profile):
        raise AssertionError("matching NVM must not be rewritten")

    monkeypatch.setattr(profile_source, "_sidecar_request", fake_request)
    monkeypatch.setattr(profile_source, "_apply_nvm_profile", must_not_apply)

    result = await apply_tic249_profile_source(source)

    assert result["nvm"]["applied"] is False
    assert calls[-1] == (
        "POST",
        "/api/config",
        {
            "motor": {"current_limit_ma": 1600},
            "limit_switches": {"limit_reaction_delay_ms": 0},
            "stop_at_limit": True,
        },
    )
    assert oql_target.read_text(encoding="utf-8") == source


@pytest.mark.asyncio
async def test_apply_refuses_profile_while_coils_are_energized(monkeypatch) -> None:
    async def fake_request(_method, _path, *, payload=None):
        del payload
        return {"velocity": 0, "energized": True}, "http://tic"

    monkeypatch.setattr(profile_source, "_sidecar_request", fake_request)

    with pytest.raises(Tic249ProfileUnsafeError, match="energized=false"):
        await apply_tic249_profile_source(_source())
