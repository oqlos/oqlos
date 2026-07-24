"""Tests for OqlOS-owned HUI hardware recipes."""

from __future__ import annotations

import asyncio
from typing import Any

from oqlos.hardware import hui_actions, hui_hold, hui_lung_recipe, hui_valve


def run(coro):
    return asyncio.run(coro)


class FakeGateway:
    def __init__(
        self,
        *,
        real: bool = False,
        plugin: Any | None = None,
        readiness: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.is_real = real
        self.plugin = plugin
        self.readiness = readiness
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

    async def plugin_readiness(self, plugin_id: str) -> dict[str, Any]:
        self.calls.append(("readiness", plugin_id))
        if self.readiness is None:
            return {"ok": True, "plugin_id": plugin_id, "status": "ok", "message": ""}
        return self.readiness.get(
            plugin_id,
            {"ok": False, "plugin_id": plugin_id, "status": "not_configured", "message": ""},
        )


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


def test_hui_hold_fails_before_shutdown_when_required_plugin_is_disabled(monkeypatch) -> None:
    monkeypatch.setattr(hui_hold, "_VALVE_STAGGER_SECONDS", 0)
    gateway = FakeGateway(
        real=True,
        readiness={
            "modbus-io": {
                "ok": False,
                "plugin_id": "modbus-io",
                "status": "disabled",
                "message": "Plugin modbus-io is disabled in OqlOS configuration",
            },
            "motor-dri0050": {
                "ok": True,
                "plugin_id": "motor-dri0050",
                "status": "ok",
                "message": "",
            },
        },
    )

    payload = run(hui_actions.start_hui_hold(gateway, "lp-pwm-plus10"))

    assert payload["ok"] is False
    assert payload["status_code"] == 503
    assert payload["error_code"] == "C2004-HW-0012"
    assert payload["required_hardware"] == ["modbus-io", "motor-dri0050"]
    assert payload["operations"] == []
    assert not any(call[0] in {"pump", "valve"} for call in gateway.calls)


def test_hui_hold_stop_reports_the_hold_that_was_started(monkeypatch) -> None:
    monkeypatch.setattr(hui_hold, "_VALVE_STAGGER_SECONDS", 0)
    gateway = FakeGateway()

    started = run(hui_actions.start_hui_hold(gateway, "lp-pwm-plus10"))
    stopped = run(hui_actions.stop_hui_hold(gateway, "lp-pwm-plus10"))

    assert started["key"] == "lp-pwm-plus10"
    assert stopped["key"] == "lp-pwm-plus10"
    assert stopped["stopped_key"] == "lp-pwm-plus10"
    assert stopped["ok"] is True


def test_hui_hold_stop_fails_fast_when_modbus_io_is_unavailable(monkeypatch) -> None:
    """Regression: stop must not hang on valve shutdown when modbus-io is dead."""
    monkeypatch.setattr(hui_hold, "_VALVE_STAGGER_SECONDS", 0)
    gateway = FakeGateway(
        real=True,
        readiness={
            "modbus-io": {
                "ok": False,
                "plugin_id": "modbus-io",
                "status": "error",
                "message": "Modbus RTU read_coils timed out after 2.0s",
            },
        },
    )
    # Pretend a hold was active so stop must clear it without touching hardware.
    hui_hold._active_hold_key = "head-inflate"  # noqa: SLF001 — test clears session state

    payload = run(hui_actions.stop_hui_hold(gateway, "head-inflate"))

    assert payload["ok"] is False
    assert payload["command"] == "hold_stop"
    assert payload["status_code"] == 503
    assert payload["error_code"] == "C2004-HW-0012"
    assert payload["required_hardware"] == ["modbus-io"]
    assert payload["key"] == "head-inflate"
    assert payload["stopped_key"] == "head-inflate"
    assert hui_hold._active_hold_key is None  # noqa: SLF001
    assert not any(call[0] in {"pump", "valve"} for call in gateway.calls)
    assert ("readiness", "modbus-io") in gateway.calls


def test_hui_hold_profile_can_be_overridden_from_hardware_map(monkeypatch) -> None:
    monkeypatch.setattr(hui_hold, "_VALVE_STAGGER_SECONDS", 0)
    # Isolate from on-disk OQL profiles so MAP override is the top layer.
    monkeypatch.setattr(hui_hold, "_oql_hui_hold_profiles", lambda: {})
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
    monkeypatch.setattr(hui_hold, "_oql_hui_hold_profiles", lambda: {})
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


def test_hui_artificial_lung_recipe_can_be_overridden_from_hardware_map(monkeypatch) -> None:
    monkeypatch.setattr(
        hui_lung_recipe,
        "_mapped_hui_lung_action_body",
        lambda: {
            "valve_id": "valve-8",
            "steps": 2000,
            "speed": 30_000_000,
            "cycles": 7,
            "pause": 0.2,
            "ramp_seconds": 0.1,
            "acceleration": 300_000_000,
        },
    )
    plugin = FakeTic249Plugin()
    gateway = FakeGateway(real=True, plugin=plugin)

    payload = run(hui_actions.start_hui_artificial_lung(gateway))

    assert payload["ok"] is True
    assert gateway.calls[0] == ("valve", "valve-8", True)
    args = plugin.commands[0][1]
    assert args["steps"] == 2000
    assert args["speed"] == 30_000_000
    assert args["cycles"] == 7
    assert args["pause"] == 0.2
    assert args["ramp_seconds"] == 0.1
    assert args["acceleration"] == 300_000_000


def test_stop_hui_artificial_lung_closes_the_configured_valve() -> None:
    """Regression: stop must not crash (was NameError: HUI_AL_LUNG_VALVE_ID) and must close the valve."""
    gateway = FakeGateway()

    payload = run(hui_actions.stop_hui_artificial_lung(gateway))

    assert payload["ok"] is True
    assert ("stop_lung",) in gateway.calls
    assert ("valve", "valve-4", False) in gateway.calls


def test_stop_hui_artificial_lung_uses_overridden_valve(monkeypatch) -> None:
    """Regression: stop must close whichever valve start would have opened, not the hardcoded default."""
    monkeypatch.setattr(
        hui_lung_recipe,
        "_mapped_hui_lung_action_body",
        lambda: {"valve_id": "valve-8"},
    )
    gateway = FakeGateway()

    payload = run(hui_actions.stop_hui_artificial_lung(gateway))

    assert payload["ok"] is True
    assert ("valve", "valve-8", False) in gateway.calls


def test_hui_artificial_lung_start_failure_cleans_up_same_valve_it_opened(monkeypatch) -> None:
    """Regression: cleanup-on-failure must close the same (possibly overridden) valve it opened."""
    monkeypatch.setattr(
        hui_lung_recipe,
        "_mapped_hui_lung_action_body",
        lambda: {"valve_id": "valve-8"},
    )

    class FailingPlugin:
        async def execute_command(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
            return {"success": False, "error": "boom"}

    gateway = FakeGateway(real=True, plugin=FailingPlugin())

    payload = run(hui_actions.start_hui_artificial_lung(gateway))

    assert payload["ok"] is False
    assert gateway.calls[0] == ("valve", "valve-8", True)
    assert gateway.calls[-1] == ("valve", "valve-8", False)


def test_hui_valve_key_can_be_overridden_from_hardware_map(monkeypatch) -> None:
    monkeypatch.setattr(hui_valve, "_oql_hui_valve_specs", lambda: {})
    monkeypatch.setattr(
        hui_valve,
        "_mapped_hui_valve_specs",
        lambda: {"wc-press": {"valve_id": "valve-8", "value": True}},
    )
    gateway = FakeGateway()

    payload = run(hui_valve.run_hui_valve_key(gateway, "wc-press"))

    assert payload["ok"] is True
    assert gateway.calls == [("valve", "valve-8", True)]


def test_hui_actions_list_includes_valve_specs(monkeypatch) -> None:
    monkeypatch.setattr(
        hui_valve,
        "_mapped_hui_valve_specs",
        lambda: {"wc-bleed": {"valve_id": "valve-wc", "value": False}},
    )

    payload = hui_actions.list_hui_actions()

    assert payload["ok"] is True
    assert "wc-press" in payload["valve_keys"]
    assert payload["valve_specs"]["wc-bleed"] == {"valve_id": "valve-wc", "value": False}


def test_hui_shutdown_turns_off_pump_and_all_known_valves() -> None:
    gateway = FakeGateway()

    payload = run(hui_actions.shutdown_all_hui_hardware(gateway))

    assert payload["ok"] is True
    assert gateway.calls[0] == ("pump", 0.0)
    off_valves = [call for call in gateway.calls if call[0] == "valve" and call[2] is False]
    assert len(off_valves) == len(hui_actions.HUI_ALL_VALVE_IDS)
