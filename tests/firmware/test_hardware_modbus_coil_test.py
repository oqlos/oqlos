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
    async def fake_read(_profile):
        return _snapshot([False, True, False, False, False, False, False, False])

    monkeypatch.setattr(coil_test, "read_modbus_profile_channels", fake_read)
    monkeypatch.setattr(
        coil_test,
        "build_coil_catalog",
        lambda states: [{"address": index, "state": value} for index, value in enumerate(states)],
    )
    plan = asyncio.run(coil_test.build_coil_test_plan())
    assert plan["ready"] is False
    assert "DO2" in plan["safety"]["blocked_reasons"][0]


def test_plan_keeps_configured_identity_when_module_does_not_respond(monkeypatch) -> None:
    async def fake_read(_profile):
        raise OqlosError(
            code="hw_modbus_no_response",
            status_code=503,
            message="No Modbus profile modules responded",
            detail={
                "profile_id": "modbus-io",
                "modules": [{
                    "module_role": "modbus-io",
                    "device_id": 2,
                    "serial_port": "/dev/serial/by-id/io-adapter",
                    "message": "read_all failed",
                }],
            },
        )

    monkeypatch.setattr(coil_test, "read_modbus_profile_channels", fake_read)
    monkeypatch.setattr(
        coil_test,
        "build_coil_catalog",
        lambda states: [
            {"address": index, "state": states[index] if index < len(states) else None}
            for index in range(MODBUS_IO_COIL_COUNT)
        ],
    )

    plan = asyncio.run(coil_test.build_coil_test_plan())

    assert plan["ok"] is False
    assert plan["ready"] is False
    assert plan["error_code"] == "C2004-HW-0012"
    assert plan["module"]["device_id"] == 2
    assert plan["module"]["serial_port"] == "/dev/serial/by-id/io-adapter"
    assert plan["safety"]["automatic_off"] is True
    assert plan["safety"]["max_pulse_ms"] == 1000
    assert plan["safety"]["blocked_reasons"] == [
        "No Modbus profile modules responded",
        "read_all failed",
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
            "coils": [],
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
