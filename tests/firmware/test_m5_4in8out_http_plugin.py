"""CoreS3 HTTP transport guards for the M5Stack valve plugin."""

from __future__ import annotations

from typing import Any

import pytest

from oqlos.hardware.plugins import M54In8OutPlugin, PluginConfig, PluginStatus
from oqlos.hardware.plugins import m5_4in8out


class _CoreS3:
    healthy = True
    instances: list["_CoreS3"] = []

    def __init__(self, base_url: str, token: str, timeout: float) -> None:
        self.base_url = base_url
        self.token = token
        self.timeout = timeout
        self.closed = False
        self.commands: list[tuple[str, dict[str, Any]]] = []
        self.__class__.instances.append(self)

    def status(self) -> dict[str, Any]:
        return {
            "data": {
                "healthy": self.healthy,
                "modules": [
                    {"address": "0x45", "firmware_version": 3},
                    {"address": "0x66", "firmware_version": 3},
                ],
            }
        }

    def execute(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        self.commands.append((command, params))
        return {"success": True, "data": {"command": command, **params}}

    def close(self) -> None:
        self.closed = True


def _config() -> PluginConfig:
    return PluginConfig(
        plugin_id="io-m5-4in8out",
        connection_type="http",
        connection_params={
            "base_url": "http://192.168.188.127:8080",
            "token": "test-token",
        },
        timeout=1.0,
        retry_count=0,
    )


@pytest.fixture(autouse=True)
def _fake_cores3(monkeypatch: pytest.MonkeyPatch) -> None:
    _CoreS3.healthy = True
    _CoreS3.instances.clear()
    monkeypatch.setattr(m5_4in8out, "CoreS3HttpClient", _CoreS3)


@pytest.mark.asyncio
async def test_http_connect_and_health_require_both_modules_ready() -> None:
    plugin = M54In8OutPlugin(_config())

    assert await plugin.connect() is True
    health = await plugin.health_check()

    assert plugin.status is PluginStatus.CONNECTED
    assert health.compatible is True
    assert health.details["address"] == "0x45, 0x66"


@pytest.mark.asyncio
async def test_http_unhealthy_gateway_is_not_compatible() -> None:
    _CoreS3.healthy = False
    plugin = M54In8OutPlugin(_config())

    assert await plugin.connect() is False
    health = await plugin.health_check()

    assert health.compatible is False
    assert health.status is PluginStatus.ERROR


@pytest.mark.asyncio
async def test_http_valve_command_uses_shared_zero_based_mapping() -> None:
    plugin = M54In8OutPlugin(_config())
    assert await plugin.connect() is True

    result = await plugin.execute_command(
        "set_valve", {"valve_id": "valve-wc", "value": True}
    )

    assert result["success"] is True
    assert _CoreS3.instances[-1].commands[-1] == (
        "set_coil",
        {"coil": 2, "value": True},
    )


@pytest.mark.asyncio
async def test_http_disconnect_closes_persistent_connection() -> None:
    plugin = M54In8OutPlugin(_config())
    assert await plugin.connect() is True
    client = _CoreS3.instances[-1]

    await plugin.disconnect()

    assert client.closed is True
    assert plugin.status is PluginStatus.CONFIGURED
