from __future__ import annotations

import asyncio

import pytest

from oqlos.api import hardware_modbus_coil_test as coil_test
from oqlos.errors import OqlosError
from oqlos.hardware.modbus_io_catalog import (
    MODBUS_IO_COIL_COUNT,
    build_coil_catalog,
    resolve_valve_coil,
)


def _snapshot(states=None):
    values = states if states is not None else [False] * MODBUS_IO_COIL_COUNT
    return {
        "ok": True,
        "modules": [{
            "module_role": "modbus-io",
            "ok": True,
            "device_id": 2,
            "serial_port": "/dev/ttyTEST",
            "config_registers": [{"id": "UART_CFG", "value": 3}],
            "channels": [
                {"kind": "digital_output", "address": index, "value": value}
                for index, value in enumerate(values)
            ],
        }],
    }


def test_catalog_is_ordered_and_aliases_are_canonical(monkeypatch) -> None:
    monkeypatch.setattr(
        "oqlos.hardware.modbus_io_catalog.runtime_coil_uses",
        lambda: {address: [] for address in range(MODBUS_IO_COIL_COUNT)},
    )
    rows = build_coil_catalog([False] * MODBUS_IO_COIL_COUNT)
    assert [row["id"] for row in rows] == [f"DO{i}" for i in range(1, 9)]
    assert resolve_valve_coil("valve-nc") == 0
    assert resolve_valve_coil("valve-wc") == 2
    assert rows[0]["aliases"] == ["valve-1", "valve-nc"]


def test_plan_blocks_when_a_coil_is_already_on(monkeypatch) -> None:
    class FakePlugin:
        async def execute_command(self, _command, _payload):
            return {
                "success": True,
                "data": {
                    "outputs": [False, True, False, False, False, False, False, False],
                    "inputs": [False] * 4,
                },
            }

    class FakeGateway:
        _plugin_configs = {}

        def valve_controllers(self):
            return ["io-m5-4in8out"]

    async def fake_controller():
        return "io-m5-4in8out", FakePlugin(), FakeGateway()

    monkeypatch.setattr(coil_test, "_controller", fake_controller)
    plan = asyncio.run(coil_test.build_coil_test_plan())
    assert plan["ready"] is False
    assert "DO2" in plan["safety"]["blocked_reasons"][0]
    assert plan["module"]["active_controller"] == "io-m5-4in8out"


def test_plan_keeps_configured_identity_when_module_does_not_respond(monkeypatch) -> None:
    async def fake_controller():
        raise OqlosError(
            code="hw_m5_4in8out_no_response",
            status_code=503,
            message="No configured valve controller is available",
            detail={
                "controllers": ["io-m5-4in8out", "modbus-io"],
                "readiness": [
                    {
                        "plugin_id": "io-m5-4in8out",
                        "message": "CoreS3 gateway unavailable",
                        "endpoint": "http://192.168.188.127:8080",
                        "transport": "http",
                    }
                ],
            },
        )

    monkeypatch.setattr(coil_test, "_controller", fake_controller)

    plan = asyncio.run(coil_test.build_coil_test_plan())

    assert plan["ok"] is False
    assert plan["ready"] is False
    assert plan["error_code"] == "C2004-HW-0012"
    assert plan["module"]["active_controller"] == "io-m5-4in8out"
    assert plan["module"]["endpoint"] == "http://192.168.188.127:8080"
    assert plan["safety"]["automatic_off"] is True
    assert plan["safety"]["max_pulse_ms"] == 1000
    assert plan["safety"]["blocked_reasons"] == [
        "No configured valve controller is available",
        "CoreS3 gateway unavailable",
    ]
    assert len(plan["coils"]) == MODBUS_IO_COIL_COUNT
    assert all(row["state"] is None for row in plan["coils"])


def test_pulse_always_switches_selected_coil_off(monkeypatch) -> None:
    calls = []

    class FakePlugin:
        async def execute_command(self, command, payload):
            calls.append((command, dict(payload)))
            return {"success": True, "data": dict(payload)}

    async def fake_plan():
        return {
            "ok": True,
            "ready": True,
            "safety": {"blocked_reasons": []},
            "coils": [{"address": index} for index in range(16)],
        }

    async def fake_plugin():
        return FakePlugin()

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(coil_test, "build_coil_test_plan", fake_plan)
    monkeypatch.setattr(coil_test, "_plugin", fake_plugin)
    monkeypatch.setattr(coil_test.asyncio, "sleep", no_sleep)

    result = asyncio.run(coil_test.pulse_coil({
        "address": 3,
        "duration_ms": 300,
        "confirm": "PULSE_DO4",
    }))

    assert result["ok"] is True
    assert calls == [
        ("set_coil", {"coil": 3, "value": True}),
        ("set_coil", {"coil": 3, "value": False}),
    ]


def test_pulse_rejects_missing_exact_confirmation() -> None:
    with pytest.raises(OqlosError) as caught:
        asyncio.run(coil_test.pulse_coil({
            "address": 0,
            "duration_ms": 300,
            "confirm": "yes",
        }))
    assert caught.value.public_code == "C2004-DATA-0002"
    assert caught.value.issue_code == "api_modbus_wizard_invalid_request"
    assert "PULSE_DO1" in caught.value.message


def test_pulse_rejects_invalid_address() -> None:
    with pytest.raises(OqlosError) as caught:
        asyncio.run(coil_test.pulse_coil({
            "address": 99,
            "duration_ms": 300,
            "confirm": "PULSE_DO100",
        }))
    assert caught.value.public_code == "C2004-DATA-0002"
    assert "address" in caught.value.message


def test_pulse_rejects_out_of_range_duration() -> None:
    with pytest.raises(OqlosError) as caught:
        asyncio.run(coil_test.pulse_coil({
            "address": 0,
            "duration_ms": 10,
            "confirm": "PULSE_DO1",
        }))
    assert caught.value.public_code == "C2004-DATA-0002"
    assert "duration_ms" in caught.value.message


def test_pulse_raises_when_preflight_blocks(monkeypatch) -> None:
    async def fake_plan():
        return {
            "ok": False,
            "ready": False,
            "safety": {"blocked_reasons": ["modbus-io is unavailable"]},
            "coils": [],
        }

    monkeypatch.setattr(coil_test, "build_coil_test_plan", fake_plan)

    with pytest.raises(OqlosError) as caught:
        asyncio.run(coil_test.pulse_coil({
            "address": 0,
            "duration_ms": 300,
            "confirm": "PULSE_DO1",
        }))
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "hw_modbus_no_response"
    assert "preflight" in caught.value.message


def test_stop_uses_waveshare_all_outputs_off(monkeypatch) -> None:
    calls = []

    class FakePlugin:
        async def execute_command(self, command, payload):
            calls.append((command, dict(payload)))
            return {"success": True, "data": {"all_outputs": True}}

    async def fake_plugin():
        return FakePlugin()

    monkeypatch.setattr(coil_test, "_plugin", fake_plugin)

    result = asyncio.run(coil_test.stop_all_coils())

    assert result["ok"] is True
    assert result["method"] == "all_outputs_off"
    assert calls == [("all_outputs_off", {})]
    assert [row["coil"] for row in result["operations"]] == [f"DO{i}" for i in range(1, 9)]
    assert all(row["ok"] for row in result["operations"])


def test_stop_falls_back_to_per_coil_when_broadcast_fails(monkeypatch) -> None:
    calls = []

    class FakePlugin:
        async def execute_command(self, command, payload):
            calls.append((command, dict(payload)))
            if command == "all_outputs_off":
                return {"success": False, "error": "broadcast rejected"}
            return {"success": True, "data": dict(payload)}

    async def fake_plugin():
        return FakePlugin()

    monkeypatch.setattr(coil_test, "_plugin", fake_plugin)

    result = asyncio.run(coil_test.stop_all_coils())

    assert result["ok"] is True
    assert result["method"] == "per_coil_fallback"
    assert calls[0] == ("all_outputs_off", {})
    assert [command for command, _payload in calls[1:]] == ["set_coil"] * MODBUS_IO_COIL_COUNT


def test_stop_raises_when_plugin_unavailable(monkeypatch) -> None:
    async def missing_plugin():
        raise OqlosError(
            code="hw_modbus_no_response",
            status_code=503,
            message="modbus-io plugin unavailable",
        )

    monkeypatch.setattr(coil_test, "_plugin", missing_plugin)

    with pytest.raises(OqlosError) as caught:
        asyncio.run(coil_test.stop_all_coils())
    assert caught.value.public_code == "C2004-HW-0012"
    assert "unavailable" in caught.value.message


def test_stop_names_failed_coils_after_broadcast_and_writes_fail(monkeypatch) -> None:
    class FakePlugin:
        async def execute_command(self, command, payload):
            if command == "all_outputs_off":
                return {"success": False, "error": "timeout"}
            return {"success": False, "error": f"DO{int(payload['coil']) + 1} write failed"}

    async def fake_plugin():
        return FakePlugin()

    monkeypatch.setattr(coil_test, "_plugin", fake_plugin)

    with pytest.raises(OqlosError) as caught:
        asyncio.run(coil_test.stop_all_coils())
    assert caught.value.public_code == "C2004-HW-0012"
    assert "DO1" in caught.value.message
    assert "all_outputs_off: timeout" in caught.value.message
    assert caught.value.detail["method"] == "per_coil_fallback"
