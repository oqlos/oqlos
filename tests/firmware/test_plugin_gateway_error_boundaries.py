"""Error-boundary contracts for the plugin hardware gateway."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from oqlos.hardware import plugin_gateway as gateway_mod
from oqlos.hardware.plugin_gateway import PluginHardwareGateway
from oqlos.hardware.plugins import PluginConfig, PluginHealth, PluginStatus


def _real_gateway() -> PluginHardwareGateway:
    gateway = PluginHardwareGateway(mode="mock")
    gateway.mode = "real"
    gateway._init_done = True
    return gateway


class _ExpectedFailurePlugin:
    async def health_check(self):
        raise RuntimeError("token=plugin-secret at /dev/private-device")

    async def connect(self):
        raise RuntimeError("token=plugin-secret at /dev/private-device")

    async def execute_command(self, _command: str, _params: dict[str, Any]):
        raise RuntimeError("token=plugin-secret at /dev/private-device")


class _ProgrammingFailurePlugin:
    async def health_check(self):
        raise AttributeError("token=plugin-secret programming defect")

    async def connect(self):
        raise AttributeError("token=plugin-secret programming defect")

    async def execute_command(self, _command: str, _params: dict[str, Any]):
        raise AttributeError("token=plugin-secret programming defect")


def test_hardware_schema_failure_is_stable_and_programming_error_propagates(
    monkeypatch,
) -> None:
    gateway = PluginHardwareGateway(mode="mock")

    def _missing_path(_config_path=None):
        raise FileNotFoundError("token=config-secret at /srv/private/config.yaml")

    monkeypatch.setattr(gateway_mod, "resolve_oqlos_config_path", _missing_path)

    with pytest.raises(RuntimeError) as caught:
        gateway._load_hardware_schema()

    assert str(caught.value) == "Failed to load OqlOS hardware configuration"
    assert "config-secret" not in str(caught.value)
    assert caught.value.__suppress_context__ is True

    def _programming_error(_config_path=None):
        raise AttributeError("token=config-secret programming defect")

    monkeypatch.setattr(
        gateway_mod, "resolve_oqlos_config_path", _programming_error
    )
    with pytest.raises(AttributeError, match="programming defect"):
        gateway._load_hardware_schema()


def test_initialization_summary_is_stable_and_programming_error_propagates(
    monkeypatch,
) -> None:
    gateway = _real_gateway()
    gateway._init_done = False
    gateway._plugin_configs = {
        "motor-dri0050": PluginConfig(plugin_id="motor-dri0050", enabled=True)
    }

    async def _expected_failure(_plugin_id: str, _config: PluginConfig):
        raise RuntimeError("token=init-secret at /srv/private/device")

    monkeypatch.setattr(gateway_mod.PluginRegistry, "create_instance", _expected_failure)

    asyncio.run(gateway._initialize_plugins())

    assert gateway.last_init_summary["failed"] == [
        {"plugin_id": "motor-dri0050", "reason": "initialization-error"}
    ]
    assert "init-secret" not in json.dumps(gateway.last_init_summary)

    gateway._init_done = False

    async def _programming_error(_plugin_id: str, _config: PluginConfig):
        raise AttributeError("token=init-secret programming defect")

    monkeypatch.setattr(gateway_mod.PluginRegistry, "create_instance", _programming_error)

    with pytest.raises(AttributeError, match="programming defect"):
        asyncio.run(gateway._initialize_plugins())
    assert gateway._init_done is False


def test_plugin_readiness_sanitizes_expected_failure_and_propagates_defect(
    monkeypatch,
) -> None:
    gateway = _real_gateway()
    gateway._plugin_configs = {
        "motor-dri0050": PluginConfig(plugin_id="motor-dri0050", enabled=True)
    }

    async def _expected_plugin(_plugin_id: str):
        return _ExpectedFailurePlugin()

    monkeypatch.setattr(gateway, "_get_or_connect_plugin", _expected_plugin)
    result = asyncio.run(gateway.plugin_readiness("motor-dri0050"))

    assert result == {
        "ok": False,
        "plugin_id": "motor-dri0050",
        "status": "error",
        "message": "Plugin health check failed",
    }
    assert "plugin-secret" not in json.dumps(result)

    async def _broken_plugin(_plugin_id: str):
        return _ProgrammingFailurePlugin()

    monkeypatch.setattr(gateway, "_get_or_connect_plugin", _broken_plugin)
    with pytest.raises(AttributeError, match="programming defect"):
        asyncio.run(gateway.plugin_readiness("motor-dri0050"))


def test_reconnect_handles_expected_failure_and_propagates_defect(monkeypatch) -> None:
    gateway = _real_gateway()
    gateway._plugin_configs = {
        "motor-dri0050": PluginConfig(plugin_id="motor-dri0050", enabled=True)
    }
    expected_plugin = _ExpectedFailurePlugin()
    monkeypatch.setattr(
        gateway_mod.PluginRegistry,
        "get_instance",
        classmethod(lambda _cls, _plugin_id: expected_plugin),
    )

    assert asyncio.run(gateway._get_or_connect_plugin("motor-dri0050")) is None

    broken_plugin = _ProgrammingFailurePlugin()
    monkeypatch.setattr(
        gateway_mod.PluginRegistry,
        "get_instance",
        classmethod(lambda _cls, _plugin_id: broken_plugin),
    )
    with pytest.raises(AttributeError, match="programming defect"):
        asyncio.run(gateway._get_or_connect_plugin("motor-dri0050"))


async def _run_operation(gateway: PluginHardwareGateway, operation: str) -> Any:
    if operation == "set_valve":
        return await gateway.set_valve("valve-1", True)
    if operation == "set_pump":
        return await gateway.set_pump(25.0)
    if operation == "read_sensor":
        return await gateway.read_sensor("ai01")
    if operation == "read_adc_channels":
        return await gateway.read_adc_channels()
    if operation == "set_lung_result":
        return await gateway.set_lung_result()
    return await gateway._execute_lung_bool_command(
        "stop",
        {},
        mock_label="STOP_LUNG",
        error_context="stop_lung",
    )


@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        ("set_valve", False),
        (
            "set_pump",
            {
                "success": False,
                "error": "Hardware plugin operation failed",
                "reason": "command-failed",
            },
        ),
        ("read_sensor", None),
        ("read_adc_channels", None),
        (
            "set_lung_result",
            {
                "success": False,
                "error": "Hardware plugin operation failed",
                "reason": "command-failed",
            },
        ),
        ("lung_bool", False),
    ],
)
def test_command_boundaries_handle_expected_failures_but_not_programming_errors(
    monkeypatch, operation: str, expected: Any
) -> None:
    async def _power_safe(*_args, **_kwargs):
        return None

    monkeypatch.setattr(gateway_mod, "ensure_power_safe", _power_safe)
    gateway = _real_gateway()
    expected_plugin = _ExpectedFailurePlugin()
    gateway._plugins = {
        "modbus-io": expected_plugin,
        "modbus-adc": expected_plugin,
        "motor-dri0050": expected_plugin,
        "motor-tic249": expected_plugin,
    }

    result = asyncio.run(_run_operation(gateway, operation))

    assert result == expected
    assert "plugin-secret" not in json.dumps(result)

    broken_plugin = _ProgrammingFailurePlugin()
    gateway._plugins = {
        "modbus-io": broken_plugin,
        "modbus-adc": broken_plugin,
        "motor-dri0050": broken_plugin,
        "motor-tic249": broken_plugin,
    }
    with pytest.raises(AttributeError, match="programming defect"):
        asyncio.run(_run_operation(gateway, operation))


def test_negative_plugin_payload_is_sanitized_and_code_is_allowlisted(
    monkeypatch,
) -> None:
    class _RejectedPlugin:
        async def execute_command(self, _command: str, _params: dict[str, Any]):
            return {
                "success": False,
                "error": "token=payload-secret at /srv/private/device",
                "error_code": "C2004-DATA-0002",
                "debug": {"password": "payload-secret"},
            }

    async def _power_safe(*_args, **_kwargs):
        return None

    monkeypatch.setattr(gateway_mod, "ensure_power_safe", _power_safe)
    gateway = _real_gateway()
    gateway._plugins["motor-dri0050"] = _RejectedPlugin()

    result = asyncio.run(gateway.set_pump(25.0))

    assert result == {
        "success": False,
        "error": "Hardware plugin operation failed",
        "reason": "command-rejected",
        "error_code": "C2004-DATA-0002",
    }
    assert "payload-secret" not in json.dumps(result)

    rejected = gateway_mod._normalize_plugin_command_result(
        {"success": False, "error_code": "C2004-HW-9999", "error": "secret"}
    )
    assert "error_code" not in rejected
    assert "secret" not in json.dumps(rejected)


def test_gateway_health_does_not_publish_plugin_health_message(monkeypatch) -> None:
    async def _health_result(cls, plugin_id: str, timeout=None):
        return PluginHealth(
            status=PluginStatus.ERROR,
            message="token=health-secret at /dev/private-device",
            compatible=False,
        )

    gateway = _real_gateway()
    gateway._plugin_configs = {
        "modbus-io": PluginConfig(plugin_id="modbus-io", enabled=True)
    }
    monkeypatch.setattr(
        gateway_mod.PluginRegistry,
        "health_check",
        classmethod(_health_result),
    )

    result = asyncio.run(gateway.health())

    assert result["modbus-io"] == {
        "status": "error",
        "message": "Plugin health is unavailable",
        "compatible": False,
    }
    assert "health-secret" not in json.dumps(result)


def test_gateway_health_forwards_allowlisted_operator_details(monkeypatch) -> None:
    async def _health_result(cls, plugin_id: str, timeout=None):
        return PluginHealth(
            status=PluginStatus.CONNECTED,
            message="token=health-secret at /dev/private-device",
            compatible=True,
            details={
                "data": {"token": "sidecar-secret"},
                "transport_reachable": True,
                "physical_healthy": False,
                "control_credentials_available": False,
                "control_lease_active": False,
                "oql_configuration_compatible": True,
                "operator_alerts": [
                    {
                        "issue_code": "hw_tic249_position_uncertain",
                        "message": "Pozycja silnika niepewna — wykonaj homing do krańcówki.",
                    }
                ],
                "runtime_status": {
                    "position_uncertain": True,
                    "reverse_limit_active": True,
                    "forward_limit_active": False,
                    "secret_field": "sidecar-secret",
                },
            },
        )

    gateway = _real_gateway()
    gateway._plugin_configs = {
        "motor-tic249": PluginConfig(plugin_id="motor-tic249", enabled=True)
    }
    monkeypatch.setattr(
        gateway_mod.PluginRegistry,
        "health_check",
        classmethod(_health_result),
    )

    result = asyncio.run(gateway.health())
    body = result["motor-tic249"]

    assert body["message"] == "Plugin is healthy"
    assert body["details"]["operator_alerts"][0]["issue_code"] == "hw_tic249_position_uncertain"
    assert body["details"]["runtime_status"]["position_uncertain"] is True
    assert body["details"]["runtime_status"]["reverse_limit_active"] is True
    assert body["details"]["transport_reachable"] is True
    assert body["details"]["physical_healthy"] is False
    assert body["details"]["control_credentials_available"] is False
    assert body["details"]["control_lease_active"] is False
    assert body["details"]["oql_configuration_compatible"] is True
    dumped = json.dumps(result)
    assert "health-secret" not in dumped
    assert "sidecar-secret" not in dumped
    assert "secret_field" not in dumped


def test_reload_configs_sanitizes_expected_failures_and_propagates_defect(
    monkeypatch,
) -> None:
    gateway = _real_gateway()

    def _missing_path(_config_path=None):
        raise FileNotFoundError("token=reload-secret at /srv/private/config.yaml")

    monkeypatch.setattr(gateway_mod, "resolve_oqlos_config_path", _missing_path)
    missing = asyncio.run(gateway.reload_configs())
    assert missing == {
        "success": False,
        "error": "Hardware configuration is unavailable",
        "reason": "config-path-unavailable",
    }
    assert "reload-secret" not in json.dumps(missing)

    monkeypatch.setattr(
        gateway_mod,
        "resolve_oqlos_config_path",
        lambda _config_path=None: Path("/srv/private/config.yaml"),
    )
    import oqlos.hardware.configuration as configuration

    def _invalid_config(*_args, **_kwargs):
        raise ValueError("token=reload-secret invalid configuration")

    monkeypatch.setattr(configuration, "load_hardware_configuration", _invalid_config)
    invalid = asyncio.run(gateway.reload_configs())
    assert invalid["reason"] == "config-load-failed"
    assert "reload-secret" not in json.dumps(invalid)

    def _programming_error(*_args, **_kwargs):
        raise AttributeError("token=reload-secret programming defect")

    monkeypatch.setattr(
        configuration, "load_hardware_configuration", _programming_error
    )
    with pytest.raises(AttributeError, match="programming defect"):
        asyncio.run(gateway.reload_configs())
