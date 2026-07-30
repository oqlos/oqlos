"""Expected and unexpected failures at optional HTTP source boundaries."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oqlos.api import state
from oqlos.errors.fastapi_integration import install_oqlos_error_handler
from oqlos.shared import http_fallback


class _Response:
    def __init__(self, payload=None, *, json_error: Exception | None = None):
        self.is_success = True
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


class _Client:
    outcomes: list[object] = []
    expected_timeout = 1.0

    def __init__(self, *, timeout: float):
        assert timeout == self.expected_timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, _source: str):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def test_expected_transport_and_json_failures_advance_to_next_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = httpx.Request("GET", "http://optional-source")
    _Client.expected_timeout = 1.0
    _Client.outcomes = [
        httpx.ConnectError("password=hunter2", request=request),
        _Response(json_error=ValueError("password=hunter2 invalid json")),
        _Response({"rows": [{"id": "safe"}]}),
    ]
    monkeypatch.setattr(http_fallback.httpx, "AsyncClient", _Client)

    result = asyncio.run(
        http_fallback.fetch_first_json(
            ["source-1", "source-2", "source-3"],
            lambda payload: payload.get("rows")
            if isinstance(payload, dict)
            else None,
            timeout_seconds=1.0,
        )
    )

    assert result == [{"id": "safe"}]


def test_programming_failure_is_not_silently_converted_to_empty_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _Client.expected_timeout = 1.0
    _Client.outcomes = [RuntimeError("password=hunter2 programming failure")]
    monkeypatch.setattr(http_fallback.httpx, "AsyncClient", _Client)

    with pytest.raises(RuntimeError, match="programming failure"):
        asyncio.run(
            http_fallback.fetch_first_json(
                ["source-1"],
                lambda payload: payload,
                timeout_seconds=1.0,
            )
        )


def test_unexpected_source_failure_is_sanitized_at_public_http_boundary(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _Client.expected_timeout = 3.0
    _Client.outcomes = [RuntimeError("password=hunter2 programming failure")]
    monkeypatch.setattr(http_fallback.httpx, "AsyncClient", _Client)
    app = FastAPI()
    install_oqlos_error_handler(app)
    app.include_router(state.router)

    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/v1/variables/fetch",
        headers={"X-Correlation-ID": "cor-source-boundary"},
    )

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["x-correlation-id"] == "cor-source-boundary"
    body = response.json()
    assert body["code"] == "C2004-SYS-0000"
    assert body["correlation_id"] == "cor-source-boundary"
    assert "hunter2" not in response.text
    assert "traceback" not in response.text.lower()
    assert "hunter2" not in caplog.text
    assert "traceback" not in caplog.text.lower()
