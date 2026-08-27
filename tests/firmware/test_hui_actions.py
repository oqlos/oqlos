"""Tests for OqlOS-owned HUI hardware recipes."""

from __future__ import annotations

import asyncio
from typing import Any

from oqlos.hardware import (
    hui_actions,
    hui_artificial_lung,
    hui_hold,
    hui_lung_recipe,
    hui_readiness,
    hui_valve,
)
from oqlos.hardware.valve_controller import gateway_valve_controllers


def run(coro):
    return asyncio.run(coro)


class FakeGateway:
    def __init__(
        self,
        *,
        real: bool = False,
        plugin: Any | None = None,
        readiness: dict[str, dict[str, Any]] | None = None,
        controllers: tuple[str, ...] = ("modbus-io",),
    ) -> None:
        self.is_real = real
        self.plugin = plugin
        self.readiness = readiness
        self.controllers = controllers
        self.calls: list[tuple[Any, ...]] = []

    def valve_controllers(self) -> list[str]:
        return list(self.controllers)

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

    async def plugin_readiness(
        self,
        plugin_id: str,
        *,
        reconnect: bool = True,
    ) -> dict[str, Any]:
        self.calls.append(("readiness", plugin_id))
        if self.readiness is None:
            return {"ok": True, "plugin_id": plugin_id, "status": "ok", "message": ""}
        return self.readiness.get(
            plugin_id,
            {"ok": False, "plugin_id": plugin_id, "status": "not_configured", "message": ""},
        )


class BulkOffGateway(FakeGateway):
    async def all_valves_off(self) -> dict[str, Any]:
        self.calls.append(("all_valves_off",))
        return {"success": True, "data": {"all_outputs": True}}


class FailingBulkOffGateway(FakeGateway):
    async def all_valves_off(self) -> dict[str, Any]:
        self.calls.append(("all_valves_off",))
        return {"success": False, "error": "bulk command unsupported"}


class ExactReplaceGateway(BulkOffGateway):
    def valve_controllers(self) -> list[str]:
        return ["io-m5-4in8out", "modbus-io"]

    def supports_exact_valve_replace(self) -> bool:
        return True

    async def replace_valves_exact(self, valve_ids: tuple[str, ...]) -> dict[str, Any]:
        self.calls.append(("replace_valves_exact", valve_ids))
        return {"success": True, "data": {"valve_ids": list(valve_ids)}}


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


def test_hui_hold_uses_exact_stacknet_replace_without_separate_bulk_off(monkeypatch) -> None:
    monkeypatch.setattr(hui_hold, "_VALVE_STAGGER_SECONDS", 0)
    gateway = ExactReplaceGateway()

    payload = run(hui_actions.start_hui_hold(gateway, "head-inflate"))

    assert payload["ok"] is True
    assert gateway.calls == [
        ("pump", 0.0),
        ("replace_valves_exact", ("valve-5", "valve-2")),
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


def test_hui_hold_active_undervoltage_fails_before_adapter_calls(monkeypatch) -> None:
    monkeypatch.setattr(hui_hold, "_VALVE_STAGGER_SECONDS", 0)
    async def _active_undervoltage(*_args, **_kwargs):
        return {
            "ok": False,
            "operation": "hold_start",
            "error": "BoardNet supply undervoltage blocks hardware actuation",
            "error_code": "C2004-HW-0014",
            "issue_code": "boardnet_undervoltage_active",
            "status_code": 503,
            "blocked_before_adapter": True,
            "safe_to_retry": False,
            "power": {
            "status": "critical",
            "errors": [
                {
                    "error_code": "C2004-HW-0014",
                    "issue_code": "boardnet_undervoltage_active",
                }
            ],
            },
        }

    monkeypatch.setattr(hui_readiness, "power_actuation_failure", _active_undervoltage)
    gateway = FakeGateway(real=True)

    payload = run(hui_actions.start_hui_hold(gateway, "lp-pwm-plus10"))

    assert payload["ok"] is False
    assert payload["status_code"] == 503
    assert payload["error_code"] == "C2004-HW-0014"
    assert payload["issue_code"] == "boardnet_undervoltage_active"
    assert payload["blocked_before_adapter"] is True
    assert payload["operations"] == []
    assert gateway.calls == []


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
    assert ("pump", 0.0) in gateway.calls
    assert not any(call[0] == "valve" for call in gateway.calls)
    assert ("readiness", "modbus-io") in gateway.calls
    assert payload["status"] == "partial"
    assert payload["executed"]["pump_off"] is True
    assert payload["confirmed"]["pump_off"] is True


def test_hui_hold_profile_can_be_overridden_from_hardware_configuration(monkeypatch) -> None:
    monkeypatch.setattr(hui_hold, "_VALVE_STAGGER_SECONDS", 0)
    # Isolate from on-disk OQL profiles so the common config is the top layer.
    monkeypatch.setattr(hui_hold, "_oql_hui_hold_profiles", lambda: {})
    monkeypatch.setattr(
        hui_hold,
        "_configured_hui_hold_profiles",
        lambda: {"head-inflate": {"valves_on": ("valve-8",), "pump_pct": 12.5}},
    )
    gateway = FakeGateway()

    payload = run(hui_actions.start_hui_hold(gateway, "head-inflate"))

    assert payload["ok"] is True
    assert gateway.calls[-2:] == [
        ("valve", "valve-8", True),
        ("pump", 12.5),
    ]


def test_hui_actions_list_uses_configured_profiles(monkeypatch) -> None:
    monkeypatch.setattr(hui_hold, "_oql_hui_hold_profiles", lambda: {})
    monkeypatch.setattr(
        hui_hold,
        "_configured_hui_hold_profiles",
        lambda: {"head-inflate": {"valves_on": ("valve-8",), "pump_pct": 12.5}},
    )
    monkeypatch.setattr(
        hui_actions,
        "resolve_valve_controller_from_config",
        lambda: "modbus-io",
    )

    payload = hui_actions.list_hui_actions()

    assert payload["ok"] is True
    assert payload["profiles"]["head-inflate"] == {
        "valves_on": ["valve-8"],
        "pump_pct": 12.5,
        "required_hardware": ["modbus-io", "motor-dri0050"],
    }
    assert payload["diagnostics"]["hui_readiness"] == "/api/v1/hardware/hui/readiness"


def test_hui_artificial_lung_uses_tic249_plugin_recipe(monkeypatch) -> None:
    monkeypatch.setattr(
        hui_artificial_lung,
        "get_hui_lung_reciprocate_args",
        hui_lung_recipe.build_hui_lung_reciprocate_args,
    )
    plugin = FakeTic249Plugin()
    gateway = FakeGateway(real=True, plugin=plugin)

    payload = run(hui_actions.start_hui_artificial_lung(gateway))

    assert payload["ok"] is True
    valve_open = ("valve", "valve-4", True)
    motor_connect = ("plugin", "motor-tic249")
    assert valve_open in gateway.calls
    assert motor_connect in gateway.calls
    assert gateway.calls.index(valve_open) < gateway.calls.index(motor_connect)
    assert plugin.commands[0][0] == "reciprocate"
    args = plugin.commands[0][1]
    assert args["direction"] == "right"
    assert args["limit_mode"] == "reverse_on_limit"
    assert args["steps"] == 1_000_000
    assert args["speed"] == 100_000_000
    assert args["pause"] == 0.5
    assert args["ramp_seconds"] == 0.5
    assert args["acceleration"] == 200_000_000


def test_hui_artificial_lung_fails_fast_before_motion_when_valve_is_unavailable() -> None:
    plugin = FakeTic249Plugin()
    gateway = FakeGateway(
        real=True,
        plugin=plugin,
        readiness={
            "modbus-io": {
                "ok": False,
                "plugin_id": "modbus-io",
                "status": "error",
                "message": "Modbus RTU read_coils timed out after 2.0s",
            },
            "motor-tic249": {
                "ok": True,
                "plugin_id": "motor-tic249",
                "status": "ok",
                "message": "",
            },
        },
    )

    payload = run(hui_actions.start_hui_artificial_lung(gateway))

    assert payload["ok"] is False
    assert payload["error_code"] == "C2004-HW-0012"
    assert payload["status_code"] == 503
    assert payload["unavailable_hardware"][0]["plugin_id"] == "modbus-io"
    assert plugin.commands == []
    assert not any(call[0] == "valve" for call in gateway.calls)


def test_hui_artificial_lung_recipe_can_be_overridden_from_hardware_configuration(monkeypatch) -> None:
    monkeypatch.setattr(hui_lung_recipe, "_oql_hui_lung_profile", lambda: {})
    monkeypatch.setattr(
        hui_lung_recipe,
        "_configured_hui_lung_profile",
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
    valve_open = ("valve", "valve-8", True)
    motor_connect = ("plugin", "motor-tic249")
    assert valve_open in gateway.calls
    assert motor_connect in gateway.calls
    assert gateway.calls.index(valve_open) < gateway.calls.index(motor_connect)
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
    monkeypatch.setattr(hui_lung_recipe, "_oql_hui_lung_profile", lambda: {})
    monkeypatch.setattr(
        hui_lung_recipe,
        "_configured_hui_lung_profile",
        lambda: {"valve_id": "valve-8"},
    )
    gateway = FakeGateway()

    payload = run(hui_actions.stop_hui_artificial_lung(gateway))

    assert payload["ok"] is True
    assert ("valve", "valve-8", False) in gateway.calls


def test_stop_hui_artificial_lung_exposes_structured_hardware_failure() -> None:
    class StopFailingGateway(FakeGateway):
        async def stop_lung(self) -> bool:
            self.calls.append(("stop_lung",))
            return False

    gateway = StopFailingGateway()

    payload = run(hui_actions.stop_hui_artificial_lung(gateway))

    assert payload["ok"] is False
    assert payload["error"] == "Artificial lung motor stop was not confirmed"
    assert payload["error_code"] == "C2004-HW-0012"
    assert payload["issue_code"] == "hw_tic249_sidecar_unreachable"
    assert payload["status_code"] == 503
    assert payload["safe_to_retry"] is True
    assert payload["unavailable_hardware_ids"] == ["motor-tic249"]
    assert ("valve", "valve-4", False) in gateway.calls


def test_stop_hui_artificial_lung_blames_the_valve_when_the_motor_stopped() -> None:
    """Regression: an unconfirmed valve close used to be reported as a missing Tic249."""

    class ValveRejectingGateway(FakeGateway):
        async def set_valve(self, valve_id: str, value: bool) -> dict[str, Any]:
            self.calls.append(("valve", valve_id, value))
            return {"success": False, "error": "rejected by controller"}

    gateway = ValveRejectingGateway()
    controllers = gateway_valve_controllers(gateway)

    payload = run(hui_actions.stop_hui_artificial_lung(gateway))

    assert payload["ok"] is False
    assert payload["error"] == "Valve valve-4 close was not confirmed"
    assert payload["public_message"] == "Valve valve-4 close was not confirmed"
    assert payload["unavailable_hardware_ids"] == controllers
    assert "motor-tic249" not in payload["unavailable_hardware_ids"]
    assert ("stop_lung",) in gateway.calls


def test_stop_hui_artificial_lung_publishes_the_motor_reason() -> None:
    """The HTTP mapper may only expose `public_message`, never the raw error."""

    class StopFailingGateway(FakeGateway):
        async def stop_lung(self) -> bool:
            self.calls.append(("stop_lung",))
            return False

    payload = run(hui_actions.stop_hui_artificial_lung(StopFailingGateway()))

    assert payload["public_message"] == "Artificial lung motor stop was not confirmed"


def test_hui_artificial_lung_start_failure_cleans_up_same_valve_it_opened(monkeypatch) -> None:
    """Regression: cleanup-on-failure must close the same (possibly overridden) valve it opened."""
    monkeypatch.setattr(hui_lung_recipe, "_oql_hui_lung_profile", lambda: {})
    monkeypatch.setattr(
        hui_lung_recipe,
        "_configured_hui_lung_profile",
        lambda: {"valve_id": "valve-8"},
    )

    class FailingPlugin:
        async def execute_command(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
            return {"success": False, "error": "boom"}

    gateway = FakeGateway(real=True, plugin=FailingPlugin())

    payload = run(hui_actions.start_hui_artificial_lung(gateway))

    assert payload["ok"] is False
    valve_open = ("valve", "valve-8", True)
    valve_close = ("valve", "valve-8", False)
    assert valve_open in gateway.calls
    assert valve_close in gateway.calls
    assert gateway.calls.index(valve_open) < gateway.calls.index(valve_close)


def test_hui_valve_key_can_be_overridden_from_hardware_configuration(monkeypatch) -> None:
    monkeypatch.setattr(hui_valve, "_oql_hui_valve_specs", lambda: {})
    monkeypatch.setattr(
        hui_valve,
        "_configured_hui_valve_specs",
        lambda: {"wc-press": {"valve_id": "valve-8", "value": True}},
    )
    gateway = FakeGateway()

    payload = run(hui_valve.run_hui_valve_key(gateway, "wc-press"))

    assert payload["ok"] is True
    assert gateway.calls == [("valve", "valve-8", True)]


def test_hui_actions_list_includes_valve_specs(monkeypatch) -> None:
    monkeypatch.setattr(
        hui_valve,
        "_configured_hui_valve_specs",
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


def test_hui_shutdown_uses_single_bulk_modbus_safe_off_when_available() -> None:
    gateway = BulkOffGateway()

    payload = run(hui_actions.shutdown_all_hui_hardware(gateway))

    assert payload["ok"] is True
    assert gateway.calls == [("pump", 0.0), ("all_valves_off",)]
    assert payload["confirmed"]["valves_off"] == list(
        hui_actions.HUI_ALL_VALVE_IDS
    )
    assert payload["duration_ms"] >= 0
    assert [item["stage"] for item in payload["timeline"]] == [
        "hui.lock_wait",
        "set_pump",
        "readiness.modbus-io",
        "all_valves_off",
        "hui.total",
    ]
    assert all(item["started_at"] for item in payload["timeline"])
    assert all(item["completed_at"] for item in payload["timeline"])


def test_hui_hold_reuses_successful_modbus_readiness_inside_shutdown(monkeypatch) -> None:
    monkeypatch.setattr(hui_hold, "_VALVE_STAGGER_SECONDS", 0)
    gateway = BulkOffGateway(real=True)

    payload = run(hui_actions.start_hui_hold(gateway, "lp-pwm-plus5"))

    assert payload["ok"] is True
    readiness_calls = [call for call in gateway.calls if call[0] == "readiness"]
    assert readiness_calls.count(("readiness", "modbus-io")) == 1
    assert readiness_calls.count(("readiness", "motor-dri0050")) == 1
    shutdown = next(
        operation for operation in payload["operations"]
        if operation["operation"] == "shutdown"
    )
    cached = next(
        item for item in shutdown["result"]["timeline"]
        if item["stage"] == "readiness.modbus-io"
    )
    assert cached["cached"] is True


def test_hui_shutdown_falls_back_to_individual_valves_after_bulk_failure() -> None:
    gateway = FailingBulkOffGateway()

    payload = run(hui_actions.shutdown_all_hui_hardware(gateway))

    assert payload["ok"] is True
    assert gateway.calls[:2] == [("pump", 0.0), ("all_valves_off",)]
    off_valves = [call for call in gateway.calls if call[0] == "valve"]
    assert len(off_valves) == len(hui_actions.HUI_ALL_VALVE_IDS)
    assert payload["confirmed"]["valves_off"] == list(
        hui_actions.HUI_ALL_VALVE_IDS
    )


def test_hui_shutdown_stops_pump_and_fails_fast_when_modbus_is_unavailable() -> None:
    gateway = FakeGateway(
        real=True,
        readiness={
            "modbus-io": {
                "ok": False,
                "plugin_id": "modbus-io",
                "status": "unavailable",
                "message": "Plugin modbus-io could not connect",
            }
        },
    )

    payload = run(hui_actions.shutdown_all_hui_hardware(gateway))

    assert payload["ok"] is False
    assert payload["command"] == "shutdown"
    assert payload["status"] == "partial"
    assert payload["error_code"] == "C2004-HW-0012"
    assert payload["unavailable_hardware"][0]["plugin_id"] == "modbus-io"
    assert payload["operations"][0]["operation"] == "set_pump"
    assert payload["executed"] == {"pump_off": True, "valves_off": []}
    assert payload["confirmed"] == {"pump_off": True, "valves_off": []}
    assert gateway.calls == [("pump", 0.0), ("readiness", "modbus-io")]


def test_hui_readiness_separates_control_blocker_from_dfr1184_telemetry() -> None:
    gateway = FakeGateway(
        real=True,
        readiness={
            "modbus-io": {
                "ok": False,
                "plugin_id": "modbus-io",
                "status": "error",
                "message": "Plugin health is not compatible",
            },
            "motor-dri0050": {
                "ok": True,
                "plugin_id": "motor-dri0050",
                "status": "connected",
                "message": "Plugin is ready",
            },
            "motor-tic249": {
                "ok": True,
                "plugin_id": "motor-tic249",
                "status": "connected",
                "message": "Plugin is ready",
            },
        },
    )

    payload = run(
        hui_readiness.build_hui_readiness(
            gateway,
            analog_input_health={
                "ok": False,
                "status": "degraded",
                "components": {
                    "usb-adc-mcp2221": {"ok": True, "status": "connected", "message": "ready"},
                    "usb-adc-dfr1184": {
                        "ok": False,
                        "status": "unavailable",
                        "message": "UART response truncated: expected 4 bytes, received 0",
                        "transport": "uart",
                        "endpoint": "/dev/serial0",
                    },
                },
            },
        )
    )

    assert payload["status"] == "degraded"
    assert payload["controls_ready"] is False
    assert payload["telemetry_ready"] is False
    assert payload["actions"]["holds"]["lp-pwm-plus10"]["unavailable_hardware"] == ["modbus-io"]
    assert payload["actions"]["shutdown"]["ready"] is True
    assert payload["actions"]["shutdown"]["full_confirmation"] is False
    assert payload["telemetry"]["components"]["usb-adc-dfr1184"]["endpoint"] == "/dev/serial0"
