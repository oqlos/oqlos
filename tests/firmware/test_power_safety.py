"""Shared BoardNet power telemetry and pre-adapter safety gate."""

from __future__ import annotations

from typing import Any

import pytest

from oqlos.api import hardware_events, hardware_gateway, plugins
from oqlos.errors import OqlosError
from oqlos.hardware import power_safety
from oqlos.hardware.plugin_gateway import PluginHardwareGateway
from oqlos.hardware.usb_diagnostics import decode_throttled


class _RealGateway:
    is_real = True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mask", "blocked"),
    [
        (0x0, False),
        (0x1, True),
        (0x10000, False),
        (0x10001, True),
    ],
)
async def test_power_gate_uses_only_active_undervoltage(
    monkeypatch: pytest.MonkeyPatch, mask: int, blocked: bool
) -> None:
    async def _sample() -> dict[str, Any]:
        return decode_throttled(f"throttled=0x{mask:x}")

    monkeypatch.setattr(power_safety, "sample_power_telemetry", _sample)

    if blocked:
        with pytest.raises(OqlosError) as caught:
            await power_safety.ensure_power_safe(
                _RealGateway(), operation="test.actuation"
            )
        assert caught.value.public_code == "C2004-HW-0014"
        assert caught.value.detail["blocked_before_adapter"] is True
    else:
        await power_safety.ensure_power_safe(_RealGateway(), operation="test.actuation")


@pytest.mark.asyncio
async def test_safe_state_bypasses_active_undervoltage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _unexpected_sample() -> dict[str, Any]:
        raise AssertionError("safe-state operations must not be power-blocked")

    monkeypatch.setattr(power_safety, "sample_power_telemetry", _unexpected_sample)

    await power_safety.ensure_power_safe(
        _RealGateway(), operation="motor.stop", safe_state=True
    )


@pytest.mark.asyncio
async def test_power_change_is_emitted_once_per_throttling_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[dict[str, Any], dict[str, Any] | None]] = []

    async def _publish(
        current: dict[str, Any], previous: dict[str, Any] | None
    ) -> None:
        events.append((current, previous))

    monkeypatch.setattr(power_safety, "_publish_power_change", _publish)
    power_safety._reset_power_event_state()

    await power_safety.observe_power_telemetry(decode_throttled("throttled=0x0"))
    await power_safety.observe_power_telemetry(decode_throttled("throttled=0x0"))
    await power_safety.observe_power_telemetry(decode_throttled("throttled=0x10000"))
    await power_safety.observe_power_telemetry(decode_throttled(None))

    assert len(events) == 3
    assert events[0][1] is None
    assert events[0][0]["active"] == []
    assert events[0][0]["historical"] == []
    assert events[1][1]["mask"] == 0
    assert events[1][0]["historical"] == ["undervoltage"]
    assert events[1][0]["source"] == "vcgencmd.get_throttled"
    assert events[1][0]["age_ms"] >= 0
    assert events[2][0]["available"] is False
    assert events[2][1]["historical"] == ["undervoltage"]


@pytest.mark.asyncio
async def test_power_change_reaches_hardware_event_stream(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    event_path = tmp_path / "hardware-events.jsonl"
    monkeypatch.setattr(hardware_events, "_event_store_path", event_path)
    hardware_events.clear_hardware_command_events(truncate_persistent=True)
    power_safety._reset_power_event_state()

    try:
        await power_safety.observe_power_telemetry(decode_throttled("throttled=0x1"))
        event = hardware_events.list_hardware_command_events(limit=1)[0]

        assert event["event_type"] == "hardware.power_state_changed"
        assert event["source"] == "oqlos-power-safety"
        assert event["aggregate_id"] == "boardnet-power"
        assert event["payload"]["current"]["active"] == ["undervoltage"]
        assert event_path.is_file()
    finally:
        hardware_events.clear_hardware_command_events(truncate_persistent=True)


@pytest.mark.asyncio
async def test_gateway_blocks_before_adapter_and_allows_deenergize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = PluginHardwareGateway(mode="mock")
    gateway.mode = "real"
    adapter_calls: list[tuple[str, dict[str, Any]]] = []

    class _Plugin:
        async def execute_command(
            self, command: str, params: dict[str, Any]
        ) -> dict[str, Any]:
            adapter_calls.append((command, params))
            return {"success": True}

    async def _plugin(_plugin_id: str) -> _Plugin:
        return _Plugin()

    async def _active() -> dict[str, Any]:
        return decode_throttled("throttled=0x1")

    monkeypatch.setattr(gateway, "_get_or_connect_plugin", _plugin)
    monkeypatch.setattr(power_safety, "sample_power_telemetry", _active)

    with pytest.raises(OqlosError):
        await gateway.set_valve("valve-1", True)
    assert adapter_calls == []

    assert await gateway.set_valve("valve-1", False) is True
    assert adapter_calls == [("set_valve", {"valve_id": "valve-1", "value": False})]


@pytest.mark.asyncio
async def test_raw_plugin_execute_is_gated_before_plugin_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _active() -> dict[str, Any]:
        return decode_throttled("throttled=0x1")

    async def _unexpected_plugin(_plugin_id: str) -> Any:
        raise AssertionError("adapter resolution must happen after the power gate")

    monkeypatch.setattr(power_safety, "sample_power_telemetry", _active)
    monkeypatch.setattr(plugins, "_resolve_plugin_instance", _unexpected_plugin)
    monkeypatch.setattr(hardware_gateway, "_gateway", _RealGateway())

    with pytest.raises(OqlosError) as caught:
        await plugins.execute_plugin_command(
            "motor-tic249", {"command": "move", "params": {"position": 10}}
        )

    assert caught.value.public_code == "C2004-HW-0014"
