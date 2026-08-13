"""HUI readiness and holds must follow the configured valve output module."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from oqlos.hardware import hui_hold, hui_readiness
from oqlos.hardware.valve_controller import M5_VALVE_CONTROLLER, MODBUS_VALVE_CONTROLLER


class _Gateway:
    """Gateway whose valve stage is the M5 module, with modbus-io absent."""

    is_real = True

    def __init__(self) -> None:
        self.probed: list[str] = []

    def valve_controllers(self) -> list[str]:
        return [M5_VALVE_CONTROLLER]

    async def plugin_readiness(self, plugin_id: str, *, reconnect: bool = True) -> dict[str, Any]:
        self.probed.append(plugin_id)
        return {"ok": True, "plugin_id": plugin_id, "status": "ok", "message": ""}

    async def set_pump(self, power_pct: float) -> dict[str, Any]:
        return {"success": True, "data": {"power_pct": power_pct}}

    async def set_valve(self, valve_id: str, value: bool) -> bool:
        return True


def test_readiness_probes_the_m5_module_instead_of_modbus() -> None:
    gateway = _Gateway()

    payload = asyncio.run(hui_readiness.build_hui_readiness(gateway))

    assert M5_VALVE_CONTROLLER in gateway.probed
    assert MODBUS_VALVE_CONTROLLER not in gateway.probed
    assert payload["actions"]["valves"]["required_hardware"] == [M5_VALVE_CONTROLLER]
    assert payload["actions"]["artificial_lung_stop"]["best_effort_hardware"] == [
        M5_VALVE_CONTROLLER
    ]
    assert payload["actions"]["shutdown"]["required_for_full_confirmation"] == [
        "motor-dri0050",
        M5_VALVE_CONTROLLER,
    ]
    assert payload["diagnostic_endpoints"]["valve_controller"] == (
        f"/api/v1/plugins/{M5_VALVE_CONTROLLER}/health"
    )


def test_hold_profiles_require_the_configured_controller() -> None:
    gateway = _Gateway()

    payload = asyncio.run(hui_readiness.build_hui_readiness(gateway))

    for action in payload["actions"]["holds"].values():
        assert action["required_hardware"][0] == M5_VALVE_CONTROLLER


@pytest.mark.asyncio
async def test_shutdown_readiness_stage_names_the_active_controller() -> None:
    gateway = _Gateway()

    result = await hui_hold.shutdown_all_hui_hardware(gateway)

    stages = [item.get("stage") for item in result.get("timeline") or []]
    assert f"readiness.{M5_VALVE_CONTROLLER}" in stages
    assert "readiness.modbus-io" not in stages
