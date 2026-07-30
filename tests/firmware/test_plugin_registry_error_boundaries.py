"""Failure-boundary contracts for the hardware plugin registry."""

from __future__ import annotations

import asyncio
import logging

import pytest

from oqlos.hardware.plugins.base import (
    HardwarePlugin,
    PluginConfig,
    PluginHealth,
    PluginStatus,
)
from oqlos.hardware.plugins.registry import (
    PluginConfigurationError,
    PluginNotRegisteredError,
    PluginRegistry,
)


class _Plugin(HardwarePlugin):
    PLUGIN_ID = "boundary-test"
    PLUGIN_NAME = "Boundary test"

    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> None:
        return None

    async def health_check(self) -> PluginHealth:
        return PluginHealth(status=PluginStatus.CONNECTED)

    def validate_config(self) -> list[str]:
        return []

    async def execute_command(
        self, command: str, params: dict[str, object]
    ) -> dict[str, object]:
        return {"success": True}


def _config() -> PluginConfig:
    return PluginConfig(plugin_id=_Plugin.PLUGIN_ID)


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PluginRegistry, "_plugins", {})
    monkeypatch.setattr(PluginRegistry, "_instances", {})


def test_create_instance_uses_typed_lookup_error() -> None:
    with pytest.raises(PluginNotRegisteredError, match="not registered"):
        asyncio.run(PluginRegistry.create_instance("missing", _config()))


def test_create_instance_uses_typed_configuration_error() -> None:
    class InvalidPlugin(_Plugin):
        def validate_config(self) -> list[str]:
            return ["invalid transport"]

    PluginRegistry.register(InvalidPlugin)

    with pytest.raises(PluginConfigurationError, match="invalid transport"):
        asyncio.run(PluginRegistry.create_instance(_Plugin.PLUGIN_ID, _config()))


def test_connect_sanitizes_expected_plugin_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "password=hunter2 /private/device"

    class FailingPlugin(_Plugin):
        async def connect(self) -> bool:
            raise OSError(secret)

    PluginRegistry.register(FailingPlugin)

    with caplog.at_level(logging.ERROR):
        result = asyncio.run(
            PluginRegistry.connect_plugin(_Plugin.PLUGIN_ID, _config())
        )

    assert result is False
    assert secret not in caplog.text
    assert "OSError" in caplog.text


def test_connect_does_not_mask_programming_defect() -> None:
    class BrokenPlugin(_Plugin):
        async def connect(self) -> bool:
            raise AttributeError("programming defect")

    PluginRegistry.register(BrokenPlugin)

    with pytest.raises(AttributeError, match="programming defect"):
        asyncio.run(PluginRegistry.connect_plugin(_Plugin.PLUGIN_ID, _config()))


def test_health_check_returns_stable_failure_without_secret(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "token=private /srv/device"

    class FailingPlugin(_Plugin):
        async def health_check(self) -> PluginHealth:
            raise RuntimeError(secret)

    instance = FailingPlugin(_config())
    PluginRegistry._instances[_Plugin.PLUGIN_ID] = instance

    with caplog.at_level(logging.ERROR):
        health = asyncio.run(PluginRegistry.health_check(_Plugin.PLUGIN_ID))

    assert health is not None
    assert health.status == PluginStatus.ERROR
    assert health.message == "Plugin health check failed"
    assert instance.status == PluginStatus.ERROR
    assert secret not in caplog.text
    assert secret not in health.model_dump_json()


def test_health_check_does_not_mask_programming_defect() -> None:
    class BrokenPlugin(_Plugin):
        async def health_check(self) -> PluginHealth:
            raise AttributeError("programming defect")

    PluginRegistry._instances[_Plugin.PLUGIN_ID] = BrokenPlugin(_config())

    with pytest.raises(AttributeError, match="programming defect"):
        asyncio.run(PluginRegistry.health_check(_Plugin.PLUGIN_ID))


def test_discovery_is_an_intentional_sanitized_third_party_boundary(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "entrypoint-secret /private/package"

    class BrokenEntryPoint:
        name = "private-entrypoint-name"

        def load(self) -> object:
            raise RuntimeError(secret)

    monkeypatch.setattr(
        "importlib.metadata.entry_points",
        lambda **_kwargs: [BrokenEntryPoint()],
    )

    with caplog.at_level(logging.ERROR):
        discovered = PluginRegistry.discover_entry_point_plugins()

    assert discovered == []
    assert "RuntimeError" in caplog.text
    assert secret not in caplog.text
    assert BrokenEntryPoint.name not in caplog.text


def test_disconnect_sanitizes_expected_failure() -> None:
    class FailingPlugin(_Plugin):
        async def disconnect(self) -> None:
            raise OSError("private disconnect detail")

    PluginRegistry._instances[_Plugin.PLUGIN_ID] = FailingPlugin(_config())

    assert asyncio.run(PluginRegistry.disconnect_plugin(_Plugin.PLUGIN_ID)) is False
    assert PluginRegistry.get_instance(_Plugin.PLUGIN_ID) is not None
