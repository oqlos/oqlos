from __future__ import annotations

import pytest

from oqlos.hardware.tic249_nvm_validation import C2004_HW_NVM_MISMATCH, check_tic249_nvm_profile


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
