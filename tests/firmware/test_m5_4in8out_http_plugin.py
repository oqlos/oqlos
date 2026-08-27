"""CoreS3 HTTP transport guards for the M5Stack valve plugin."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from oqlos.hardware.plugins import M54In8OutPlugin, PluginConfig, PluginStatus
from oqlos.hardware.plugins import m5_4in8out


class _CoreS3:
    healthy = True
    configured = True
    active_revision = 1
    lease_error: Exception | None = None
    renew_error: Exception | None = None
    instances: list["_CoreS3"] = []

    def __init__(self, base_url: str, token: str, timeout: float, capability_client=None) -> None:
        self.base_url = base_url
        self.token = token
        self.timeout = timeout
        self.capability_client = capability_client
        self.closed = False
        self.lease_id = ""
        self.commands: list[tuple[str, dict[str, Any]]] = []
        self.__class__.instances.append(self)

    def status(self) -> dict[str, Any]:
        return {
            "data": {
                "healthy": self.healthy,
                "outputs": [False] * 16,
                "inputs": [True] * 8,
                "modules": [
                    {"address": "0x45", "firmware_version": 3},
                    {"address": "0x66", "firmware_version": 3},
                ],
                "network_interface": {"effective": "wifi"},
                "firmware": {
                    "version": "1.7.1",
                    "oql_compatibility": {
                        "configured": self.configured,
                        "compatible": self.configured,
                        "active_schema": "stacknet-runtime-v1",
                        "active_revision": self.active_revision,
                    }
                },
            }
        }

    def execute(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        self.commands.append((command, params))
        if command == "config_apply":
            self.configured = True
            self.active_revision = int(params["config_revision"])
        return {"success": True, "data": {"command": command, **params}}

    def acquire_lease(self, lease_id: str, ttl_ms: int) -> dict[str, Any]:
        if self.lease_error is not None:
            raise self.lease_error
        self.lease_id = lease_id
        return {"success": True, "data": {"lease_id": lease_id, "ttl_ms": ttl_ms}}

    def renew_lease(self) -> dict[str, Any]:
        if self.renew_error is not None:
            raise self.renew_error
        return {"success": True, "data": {"lease_id": self.lease_id}}

    def release_lease(self) -> dict[str, Any]:
        self.lease_id = ""
        return {"success": True}

    def set_output(self, output: int, value: bool) -> dict[str, Any]:
        return self.execute("set_coil", {"coil": output - 1, "value": value})

    def close(self) -> None:
        self.closed = True


def _config(*, token: str = "test-token") -> PluginConfig:
    return PluginConfig(
        plugin_id="io-m5-4in8out",
        connection_type="http",
        connection_params={
            "base_url": "http://192.168.188.127:8080",
            "token": token,
            "runtime_configuration": {
                "hostname": "stacknet",
                "ipv4_mode": "dhcp",
                "ipv4_address": "",
                "ipv4_gateway": "",
                "ipv4_netmask": "",
                "ipv4_dns": "",
                "m122_addresses": [0x45, 0x66],
                "config_schema": "stacknet-runtime-v1",
                "config_revision": 2,
                "control_api_version": 3,
            },
        },
        timeout=1.0,
        retry_count=0,
    )


@pytest.fixture(autouse=True)
def _fake_cores3(monkeypatch: pytest.MonkeyPatch) -> None:
    _CoreS3.healthy = True
    _CoreS3.configured = True
    _CoreS3.active_revision = 1
    _CoreS3.lease_error = None
    _CoreS3.renew_error = None
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
    assert health.details["physical_healthy"] is True
    assert health.details["control_lease_active"] is True


@pytest.mark.asyncio
async def test_http_health_does_not_promote_physical_gateway_without_control_lease() -> None:
    _CoreS3.lease_error = RuntimeError("lease denied")
    plugin = M54In8OutPlugin(_config())

    assert await plugin.connect() is False
    health = await plugin.health_check()

    assert health.status is PluginStatus.ERROR
    assert health.compatible is False
    assert health.details["physical_healthy"] is True
    assert health.details["control_lease_active"] is False
    assert "control lease unavailable" in health.message


@pytest.mark.asyncio
async def test_http_gateway_without_credentials_stays_visible_but_read_only() -> None:
    plugin = M54In8OutPlugin(_config(token=""))

    assert plugin.validate_config() == []
    assert await plugin.connect() is True
    health = await plugin.health_check()
    command = await plugin.execute_command("set_coil", {"coil": 0, "value": True})

    assert plugin.status is PluginStatus.CONNECTED
    assert health.status is PluginStatus.ERROR
    assert health.compatible is False
    assert health.details["physical_healthy"] is True
    assert health.details["control_credentials_available"] is False
    assert "control authorization unavailable" in health.message
    assert command == {
        "success": False,
        "error": "StackNet control authorization unavailable; read-only connection",
    }
    assert _CoreS3.instances[-1].commands == []


@pytest.mark.asyncio
async def test_http_read_only_gateway_still_serves_io_snapshot() -> None:
    plugin = M54In8OutPlugin(_config(token=""))

    assert await plugin.connect() is True
    result = await plugin.execute_command("read_io_snapshot", {})

    assert result["success"] is True
    assert result["data"]["coils"] == [False] * 16
    assert result["data"]["discrete_inputs"] == [True] * 8
    assert result["data"]["physical_healthy"] is True
    assert result["data"]["control_ready"] is False
    assert result["data"]["firmware_version"] == "1.7.1"
    assert result["data"]["address"] == "0x45, 0x66"
    assert result["data"]["modules"] == [
        {"address": "0x45", "firmware_version": 3},
        {"address": "0x66", "firmware_version": 3},
    ]
    assert result["data"]["network_interface"] == {"effective": "wifi"}
    assert _CoreS3.instances[-1].commands == []


@pytest.mark.asyncio
async def test_http_snapshot_recovers_after_startup_transport_failure() -> None:
    plugin = M54In8OutPlugin(_config(token=""))

    result = await plugin.execute_command("read_io_snapshot", {})

    assert result["success"] is True
    assert result["data"]["physical_healthy"] is True
    assert result["data"]["control_ready"] is False
    assert plugin._module is None
    assert _CoreS3.instances[-1].commands == []


@pytest.mark.asyncio
async def test_http_unhealthy_gateway_is_not_compatible() -> None:
    _CoreS3.healthy = False
    plugin = M54In8OutPlugin(_config())

    assert await plugin.connect() is True
    health = await plugin.health_check()
    command = await plugin.execute_command("set_coil", {"coil": 0, "value": True})

    assert plugin.status is PluginStatus.CONNECTED
    assert health.compatible is False
    assert health.status is PluginStatus.ERROR
    assert health.details["transport_reachable"] is True
    assert health.details["physical_healthy"] is False
    assert command == {
        "success": False,
        "error": "StackNet control lease unavailable; read-only connection",
    }
    assert _CoreS3.instances[-1].commands == []


@pytest.mark.asyncio
async def test_http_connect_applies_and_confirms_missing_oql_configuration() -> None:
    _CoreS3.configured = False
    _CoreS3.active_revision = 0
    plugin = M54In8OutPlugin(_config())

    assert await plugin.connect() is True
    health = await plugin.health_check()

    assert health.compatible is True
    assert health.details["oql_configuration_compatible"] is True
    assert any(command == "config_apply" for command, _params in _CoreS3.instances[-1].commands)


def test_core_http_config_apply_includes_the_active_lease(monkeypatch) -> None:
    from oqlos.hardware.plugins._m5_core_http import CoreS3HttpClient

    client = CoreS3HttpClient("http://stacknet.local:8080")
    client.lease_id = "boardnet:test"
    seen = {}

    def _request(path, body=None):
        seen.update({"path": path, "body": body})
        return {"success": True}

    monkeypatch.setattr(client, "_request", _request)
    client.execute("config_apply", {"config_revision": 1})

    assert seen["body"]["params"]["lease_id"] == "boardnet:test"


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
async def test_http_exact_valve_replace_uses_one_output_mask_command() -> None:
    plugin = M54In8OutPlugin(_config())
    assert await plugin.connect() is True

    result = await plugin.execute_command(
        "replace_valves", {"valve_ids": ["valve-5", "valve-2"]}
    )

    assert result["success"] is True
    assert _CoreS3.instances[-1].commands[-1] == (
        "replace_outputs",
        {"mask": (1 << 4) | (1 << 1)},
    )


@pytest.mark.asyncio
async def test_http_disconnect_closes_persistent_connection() -> None:
    plugin = M54In8OutPlugin(_config())
    assert await plugin.connect() is True
    client = _CoreS3.instances[-1]

    await plugin.disconnect()

    assert client.closed is True
    assert plugin.status is PluginStatus.CONFIGURED


@pytest.mark.asyncio
async def test_http_lease_renewal_reacquires_before_giving_up(monkeypatch) -> None:
    """One refused renewal must not keep the valve stage dead until a restart."""
    plugin = M54In8OutPlugin(_config())
    assert await plugin.connect() is True
    client = _CoreS3.instances[-1]

    failures = {"count": 1}

    def _renew_once_then_fail() -> dict[str, Any]:
        if failures["count"]:
            failures["count"] -= 1
            raise RuntimeError("CoreS3 HTTP failed: HTTP 409: ESP_ERR_INVALID_STATE")
        return {"success": True, "data": {"lease_id": client.lease_id}}

    monkeypatch.setattr(client, "renew_lease", _renew_once_then_fail)
    client.lease_id = ""

    assert await plugin._reacquire_http_lease() is True
    assert client.lease_id == plugin._lease_id
    assert plugin.status is PluginStatus.CONNECTED

    await plugin.disconnect()


@pytest.mark.asyncio
async def test_http_lease_renewal_errors_out_when_reacquire_is_refused() -> None:
    plugin = M54In8OutPlugin(_config())
    assert await plugin.connect() is True
    client = _CoreS3.instances[-1]
    client.lease_error = RuntimeError("lease denied")

    assert await plugin._reacquire_http_lease() is False

    await plugin.disconnect()


async def _wait_for_status(plugin, status, *, timeout: float = 3.0) -> bool:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if plugin.status is status:
            return True
        await asyncio.sleep(0.05)
    return plugin.status is status


@pytest.mark.asyncio
async def test_http_lease_renewal_failure_marks_plugin_unavailable() -> None:
    config = _config()
    config.connection_params["lease_ttl_ms"] = 500
    plugin = M54In8OutPlugin(config)
    assert await plugin.connect() is True
    # Renewal *and* re-acquire refused: nothing can re-arm the lease, so the
    # plugin must end up unavailable rather than pretending it can still drive.
    _CoreS3.renew_error = RuntimeError("MaskAuth unavailable")
    _CoreS3.lease_error = RuntimeError("MaskAuth unavailable")

    assert await _wait_for_status(plugin, PluginStatus.ERROR)

    health = await plugin.health_check()
    assert health.compatible is False
    assert health.details["control_lease_active"] is False
    await plugin.disconnect()


@pytest.mark.asyncio
async def test_http_lease_renewal_failure_recovers_when_reacquire_succeeds() -> None:
    """One refused renewal must not brick the valve stage until a restart."""
    config = _config()
    config.connection_params["lease_ttl_ms"] = 500
    plugin = M54In8OutPlugin(config)
    assert await plugin.connect() is True
    _CoreS3.renew_error = RuntimeError("HTTP 409: ESP_ERR_INVALID_STATE")

    await asyncio.sleep(0.6)

    assert plugin.status is PluginStatus.CONNECTED
    await plugin.disconnect()
