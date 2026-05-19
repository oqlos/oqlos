"""Tests for artificial-lung logical command dispatch."""

from __future__ import annotations

import pytest

from oqlos.hardware import artificial_lung


@pytest.fixture(autouse=True)
def _reset_lung_state() -> None:
    artificial_lung.LUNG_STATE.update({"running": False, "lpm": 0, "status": "stopped"})


@pytest.mark.asyncio
async def test_set_lpm_updates_state() -> None:
    result = await artificial_lung.execute_command("set_lpm", {"lpm": 12}, gateway=None)

    assert result["ok"] is True
    assert artificial_lung.LUNG_STATE["lpm"] == 12
    assert artificial_lung.LUNG_STATE["status"] == "configured"


@pytest.mark.asyncio
async def test_emergency_stop_resets_lpm() -> None:
    artificial_lung.LUNG_STATE.update({"running": True, "lpm": 20, "status": "running"})

    result = await artificial_lung.execute_command("emergency_stop", {}, gateway=None)

    assert result["ok"] is True
    assert artificial_lung.LUNG_STATE["lpm"] == 0
    assert artificial_lung.LUNG_STATE["status"] == "emergency_stopped"


@pytest.mark.asyncio
async def test_get_peripheral_status_includes_logical_state() -> None:
    artificial_lung.LUNG_STATE.update({"running": True, "lpm": 8, "status": "running"})

    status = await artificial_lung.get_peripheral_status(gateway=None)

    assert status["ok"] is True
    assert status["result"]["data"]["lpm"] == 8
    assert status["result"]["data"]["running"] is True
