"""Failure-boundary contracts for the artificial-lung plugin."""

from __future__ import annotations

import asyncio
import logging

import httpx
import pytest

from oqlos.hardware.plugins import lung as lung_module
from oqlos.hardware.plugins.base import PluginConfig, PluginStatus
from oqlos.hardware.plugins.lung import LungPlugin
from oqlos.hardware.plugins.plugin_http_handlers import http_get_command


class _Response:
    def __init__(self, payload: object, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code

    def json(self) -> object:
        if isinstance(self.payload, BaseException):
            raise self.payload
        return self.payload


def _plugin(client: object | None = None) -> LungPlugin:
    plugin = LungPlugin(
        PluginConfig(
            plugin_id="motor-tic249",
            connection_type="http",
            connection_params={"base_url": "http://localhost:8205"},
        )
    )
    plugin._client = client  # type: ignore[assignment]
    return plugin


def test_connect_sanitizes_expected_transport_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "token=private /srv/tic249"
    request = httpx.Request("GET", "http://localhost:8205/health")

    class Client:
        async def get(self, _url: str) -> None:
            raise httpx.ConnectError(secret, request=request)

    monkeypatch.setattr(lung_module.httpx, "AsyncClient", lambda **_kwargs: Client())

    with caplog.at_level(logging.ERROR, logger=lung_module.__name__):
        plugin = _plugin()
        connected = asyncio.run(plugin.connect())

    assert connected is False
    assert plugin.status == PluginStatus.ERROR
    assert secret not in caplog.text
    assert "ConnectError" in caplog.text


def test_connect_does_not_mask_programming_defect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Client:
        async def get(self, _url: str) -> None:
            raise AttributeError("programming defect")

    monkeypatch.setattr(lung_module.httpx, "AsyncClient", lambda **_kwargs: Client())

    with pytest.raises(AttributeError, match="programming defect"):
        asyncio.run(_plugin().connect())


def test_health_returns_stable_failure_without_exception_detail(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "password=hunter2 /private/health"

    class Client:
        async def get(self, _url: str) -> None:
            raise RuntimeError(secret)

    with caplog.at_level(logging.ERROR, logger=lung_module.__name__):
        health = asyncio.run(_plugin(Client()).health_check())

    assert health.status == PluginStatus.ERROR
    assert health.message == "Lung motor health check failed"
    assert secret not in health.model_dump_json()
    assert secret not in caplog.text


def test_health_does_not_mask_programming_defect() -> None:
    class Client:
        async def get(self, _url: str) -> None:
            raise AttributeError("programming defect")

    with pytest.raises(AttributeError, match="programming defect"):
        asyncio.run(_plugin(Client()).health_check())


def test_invalid_runtime_json_blocks_motion_with_catalogued_failure() -> None:
    class Client:
        def __init__(self) -> None:
            self.posted = False

        async def get(self, _url: str) -> _Response:
            return _Response(ValueError("private malformed payload"))

        async def post(self, _url: str, json: object = None) -> _Response:
            self.posted = True
            return _Response({"success": True})

    client = Client()
    result = asyncio.run(_plugin(client).execute_command("reciprocate", {}))

    assert result["success"] is False
    assert result["status_code"] == 503
    assert result["error_code"] == "C2004-HW-0012"
    assert result["data"] == {}
    assert "private" not in str(result)
    assert client.posted is False


def test_command_sanitizes_expected_transport_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "secret-command /private/path"
    request = httpx.Request("POST", "http://localhost:8205/api/stop")

    class Client:
        async def post(self, _url: str, json: object = None) -> None:
            raise httpx.ConnectError(secret, request=request)

    with caplog.at_level(logging.ERROR, logger=lung_module.__name__):
        result = asyncio.run(_plugin(Client()).execute_command("stop", {}))

    assert result["success"] is False
    assert result["error_code"] == "C2004-HW-0012"
    assert result["reason"] == "command-failed"
    assert secret not in str(result)
    assert secret not in caplog.text


def test_command_does_not_mask_programming_defect() -> None:
    class Client:
        async def post(self, _url: str, json: object = None) -> None:
            raise AttributeError("programming defect")

    with pytest.raises(AttributeError, match="programming defect"):
        asyncio.run(_plugin(Client()).execute_command("stop", {}))


def test_unknown_command_does_not_echo_user_input() -> None:
    result = asyncio.run(_plugin(object()).execute_command("private-command-token", {}))

    assert result["status_code"] == 422
    assert result["error_code"] == "C2004-DATA-0002"
    assert "private-command-token" not in str(result)


def test_http_payload_decoder_does_not_mask_response_defect() -> None:
    class Client:
        async def get(self, _url: str) -> _Response:
            return _Response(AttributeError("broken response object"))

    with pytest.raises(AttributeError, match="broken response object"):
        asyncio.run(http_get_command(Client(), "http://localhost:8205", "/status"))
