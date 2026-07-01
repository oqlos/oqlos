"""Tests for OqlOS-owned HUI hardware recipes."""

from __future__ import annotations

import asyncio
from typing import Any

from oqlos.hardware import hui_actions, hui_hold


def run(coro):
    return asyncio.run(coro)


class FakeGateway:
    def __init__(self, *, real: bool = False, plugin: Any | None = None) -> None:
        self.is_real = real
        self.plugin = plugin
        self.calls: list[tuple[Any, ...]] = []

    async def set_valve(self, valve_id: str, value: bool) -> bool:
        self.calls.append(("valve", valve_id, value))
        return True

    async def set_pump(self, power_pct: float) -> dict[str, Any]:
        self.calls.append(("pump", power_pct))
        return {"success": True, "data": {"power_pct": power_pct}}

    async def set_lung_result(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("set_lung_result", kwargs))
        return {"success": True, "data": kwargs}

    async def stop_lung(self) -> bool:
        self.calls.append(("stop_lung",))
        return True

    async def _get_or_connect_plugin(self, plugin_id: str) -> Any:
        self.calls.append(("plugin", plugin_id))
        return self.plugin


class FakeTic249Plugin:
    def __init__(self) -> None:
        self.commands: list[tuple[str, dict[str, Any]]] = []

    async def execute_command(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        self.commands.append((command, params))
        return {"success": True, "data": {"command": command, "params": params}}


def test_hui_hold_profile_runs_inside_oqlos(monkeypatch) -> None:
    monkeypatch.setattr(hui_hold, "_VALVE_STAGGER_SECONDS", 0)
    gateway = FakeGateway()

    payload = run(hui_actions.start_hui_hold(gateway, "head-inflate"))

    assert payload["ok"] is True
    assert gateway.calls[-3:] == [
        ("valve", "valve-5", True),
        ("valve", "valve-2", True),
        ("pump", 70.0),
    ]


def test_hui_hold_profile_can_be_overridden_from_hardware_map(monkeypatch) -> None:
    monkeypatch.setattr(hui_hold, "_VALVE_STAGGER_SECONDS", 0)
    monkeypatch.setattr(
        hui_hold,
        "_mapped_hui_hold_profiles",
        lambda: {"head-inflate": {"valves_on": ("valve-8",), "pump_pct": 12.5}},
    )
    gateway = FakeGateway()

    payload = run(hui_actions.start_hui_hold(gateway, "head-inflate"))

    assert payload["ok"] is True
    assert gateway.calls[-2:] == [
        ("valve", "valve-8", True),
        ("pump", 12.5),
    ]


def test_hui_actions_list_uses_mapped_profiles(monkeypatch) -> None:
    monkeypatch.setattr(
        hui_hold,
        "_mapped_hui_hold_profiles",
        lambda: {"head-inflate": {"valves_on": ("valve-8",), "pump_pct": 12.5}},
    )

    payload = hui_actions.list_hui_actions()

    assert payload["ok"] is True
    assert payload["profiles"]["head-inflate"] == {"valves_on": ["valve-8"], "pump_pct": 12.5}


def test_hui_artificial_lung_uses_tic249_plugin_recipe() -> None:
    plugin = FakeTic249Plugin()
    gateway = FakeGateway(real=True, plugin=plugin)

    payload = run(hui_actions.start_hui_artificial_lung(gateway))

    assert payload["ok"] is True
    assert gateway.calls[0] == ("valve", "valve-4", True)
    assert plugin.commands[0][0] == "reciprocate"
    args = plugin.commands[0][1]
    assert args["direction"] == "right"
    assert args["limit_mode"] == "reverse_on_limit"
    assert args["steps"] == 1_000_000
    assert args["speed"] == 100_000_000
    assert args["pause"] == 0.5
    assert args["ramp_seconds"] == 0.5
    assert args["acceleration"] == 200_000_000


def test_hui_shutdown_turns_off_pump_and_all_known_valves() -> None:
    gateway = FakeGateway()

    payload = run(hui_actions.shutdown_all_hui_hardware(gateway))

    assert payload["ok"] is True
    assert gateway.calls[0] == ("pump", 0.0)
    off_valves = [call for call in gateway.calls if call[0] == "valve" and call[2] is False]
    assert len(off_valves) == len(hui_actions.HUI_ALL_VALVE_IDS)
