from __future__ import annotations

import pytest

from oqlos.hardware.tic249_nvm_validation import C2004_HW_NVM_MISMATCH, check_tic249_nvm_profile
from oqlos.hardware.tic249_nvm_validation import _interpret_nvm_validation


def test_nvm_mismatch_preserves_evidence_and_canonical_identity():
    payload = {"ok": False, "detail": "pin mismatch", "mismatches": ["SCL"]}
    result = _interpret_nvm_validation(payload)
    assert result["validation"] is payload
    assert result["detail"] == "pin mismatch"
    assert result["code"] == result["error_code"] == C2004_HW_NVM_MISMATCH
    assert result["success"] is False


def test_hardware_failure_rejects_unknown_code():
    from oqlos.hardware.plugins._shared import hardware_failure_payload
    with pytest.raises(ValueError, match="Unknown hardware failure code"):
        hardware_failure_payload("invalid", component="test")


@pytest.mark.parametrize("payload, expected", [
    ({"skipped": "disabled", "warning": "notice", "ok": True}, {"ok": True, "skipped": "disabled"}),
    ({"warning": "notice", "ok": True}, {"ok": True, "warning": "notice"}),
    ({"ok": True, "profile_id": "profile"}, {"ok": True, "profile_id": "profile"}),
])
def test_interpret_nvm_validation_preserves_evidence_precedence(payload, expected):
    result = _interpret_nvm_validation(payload)
    if "skipped" in payload or "warning" in payload:
        assert result.pop("detail") is payload
    assert result == expected


@pytest.mark.asyncio
async def test_check_tic249_nvm_profile_accepts_ok_response(monkeypatch):
    class FakeResponse:
        def json(self):
            return {"ok": True, "profile_id": "boardnet-tic249-limit-switches-v1"}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url: str):
            assert url.endswith("/api/nvm-validation")
            return FakeResponse()

    monkeypatch.setattr("oqlos.hardware.tic249_nvm_validation.httpx.AsyncClient", lambda **kwargs: FakeClient())

    result = await check_tic249_nvm_profile()
    assert result["ok"] is True
    assert result["profile_id"] == "boardnet-tic249-limit-switches-v1"


@pytest.mark.asyncio
async def test_check_tic249_nvm_profile_marks_degraded_on_mismatch(monkeypatch):
    class FakeResponse:
        def json(self):
            return {"ok": False, "error_code": C2004_HW_NVM_MISMATCH, "mismatches": []}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url: str):
            return FakeResponse()

    monkeypatch.setattr("oqlos.hardware.tic249_nvm_validation.httpx.AsyncClient", lambda **kwargs: FakeClient())

    result = await check_tic249_nvm_profile()
    assert result["ok"] is False
    assert result["error_code"] == C2004_HW_NVM_MISMATCH


@pytest.mark.asyncio
async def test_check_tic249_nvm_profile_warns_when_sidecar_unreachable(monkeypatch):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url: str):
            raise OSError("connection refused")

    monkeypatch.setattr("oqlos.hardware.tic249_nvm_validation.httpx.AsyncClient", lambda **kwargs: FakeClient())

    result = await check_tic249_nvm_profile()
    assert result["ok"] is True
    assert result["skipped"] == "sidecar_unreachable"
