"""Tests for artificial lung (tic249) integration across all layers.

Layer 1: DSL parser — SET 'płuco' / TASK [włącz] [lung] → SET_LUNG step
Layer 2: ScenarioOrchestrator — SET_LUNG → hardware.set_lung() / stop_lung()
Layer 3: FirmwareAdapter — dispatch_action / set_peripheral → POST /lung
Layer 4: CQL interpreter — → Lung.start / Lung.stop → firmware adapter
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oqlos.core._dsl_helpers import (
    _looks_like_lung_object,
    _map_action_value,
    _map_lung_action,
    _map_peripheral,
)
from oqlos.core.parser import parse_dsl_to_goal
from oqlos.hardware.firmware_adapter import FirmwareAdapter, _PERIPHERAL_MAP
from oqlos.hardware.gateway import HardwareGateway


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 1 — DSL parser helpers
# ═══════════════════════════════════════════════════════════════════════════════


class TestLungDslHelpers:
    @pytest.mark.parametrize("obj", ["lung", "płuco", "pluco", "respirator", "Lung motor"])
    def test_looks_like_lung_object(self, obj):
        assert _looks_like_lung_object(obj) is True

    def test_not_lung_object(self):
        assert _looks_like_lung_object("pump") is False
        assert _looks_like_lung_object("valve") is False

    def test_map_peripheral_lung(self):
        assert _map_peripheral("lung") == "lung-main"
        assert _map_peripheral("płuco") == "lung-main"
        assert _map_peripheral("pluco") == "lung-main"
        assert _map_peripheral("respirator") == "lung-main"

    def test_map_lung_action_start(self):
        action, value, _, _ = _map_lung_action("włącz", "lung 10", "włącz lung 10")
        assert action == "SET_LUNG"
        assert value == 10

    def test_map_lung_action_stop(self):
        action, value, _, _ = _map_lung_action("stop", "lung", "stop lung")
        assert action == "SET_LUNG"
        assert value == 0

    def test_map_lung_action_default_cycles(self):
        action, value, _, _ = _map_lung_action("start", "lung", "start lung")
        assert action == "SET_LUNG"
        assert value == 5  # default

    def test_map_action_value_lung(self):
        action, value, _, _ = _map_action_value("włącz", "lung", "lung 3", "włącz lung 3", 1)
        assert action == "SET_LUNG"
        assert value == 3


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 1b — DSL parser full round-trip
# ═══════════════════════════════════════════════════════════════════════════════


class TestLungDslParser:
    def test_parses_lung_set_command(self):
        dsl = """SCENARIO: Lung test
GOAL: Reciprocate
  SET 'płuco' '5'
"""
        goal = parse_dsl_to_goal(dsl, "lung-set")
        assert goal is not None
        assert len(goal.steps) == 1
        assert goal.steps[0].action == "SET_LUNG"
        assert goal.steps[0].peripheral == "lung-main"
        assert goal.steps[0].value == 5

    def test_parses_lung_task_command(self):
        dsl = """SCENARIO: Lung task
GOAL: Start
  TASK: [Włącz] [Lung]
"""
        goal = parse_dsl_to_goal(dsl, "lung-task")
        assert goal is not None
        assert len(goal.steps) == 1
        assert goal.steps[0].action == "SET_LUNG"
        assert goal.steps[0].peripheral == "lung-main"

    def test_parses_lung_stop(self):
        dsl = """SCENARIO: Lung stop
GOAL: Stop
  SET 'lung' '0'
"""
        goal = parse_dsl_to_goal(dsl, "lung-stop")
        assert goal is not None
        assert len(goal.steps) == 1
        assert goal.steps[0].action == "SET_LUNG"
        assert goal.steps[0].value == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 2 — ScenarioOrchestrator._execute_lung_step
# ═══════════════════════════════════════════════════════════════════════════════


class TestLungExecutor:
    def _make_orchestrator(self):
        from oqlos.core.executor import ScenarioOrchestrator
        from oqlos.models.scenario import Step

        state_manager = MagicMock()
        state_manager.peripherals = {}
        hardware = MagicMock()
        hardware.set_lung = AsyncMock(return_value=True)
        hardware.stop_lung = AsyncMock(return_value=True)

        orch = ScenarioOrchestrator(state_manager, hardware)
        orch.log_event = AsyncMock()
        return orch, hardware, Step

    def test_execute_lung_step_reciprocate(self):
        orch, hw, Step = self._make_orchestrator()
        step = Step(id="s1", action="SET_LUNG", value=3, label="lung 3 cycles")
        asyncio.run(orch._execute_lung_step(step, "auto"))
        hw.set_lung.assert_awaited_once_with(cycles=3)
        hw.stop_lung.assert_not_awaited()

    def test_execute_lung_step_stop(self):
        orch, hw, Step = self._make_orchestrator()
        step = Step(id="s2", action="SET_LUNG", value=0, label="lung stop")
        asyncio.run(orch._execute_lung_step(step, "auto"))
        hw.stop_lung.assert_awaited_once()
        hw.set_lung.assert_not_awaited()

    def test_execute_step_dispatches_set_lung(self):
        orch, hw, Step = self._make_orchestrator()
        step = Step(id="s3", action="SET_LUNG", value=5, label="lung 5")
        asyncio.run(orch.execute_step(step, "auto", 1.0))
        hw.set_lung.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 3 — FirmwareAdapter (unit, no HTTP)
# ═══════════════════════════════════════════════════════════════════════════════


class TestFirmwareAdapterLung:
    def test_peripheral_map_lung(self):
        assert _PERIPHERAL_MAP["lung"] == "lung-main"
        assert _PERIPHERAL_MAP["lung-main"] == "lung-main"
        assert _PERIPHERAL_MAP["płuco"] == "lung-main"
        assert _PERIPHERAL_MAP["pluco"] == "lung-main"

    def test_resolve_peripheral_lung(self):
        fw = FirmwareAdapter.__new__(FirmwareAdapter)
        fw.base_url = "http://localhost:8202"
        fw.timeout = 5.0
        fw._client = None
        assert fw._resolve_peripheral("Lung") == "lung-main"
        assert fw._resolve_peripheral("płuco") == "lung-main"

    def test_dispatch_lung_start(self):
        fw = FirmwareAdapter.__new__(FirmwareAdapter)
        fw.base_url = "http://localhost:8202"
        fw.timeout = 5.0
        fw._client = None

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "cycles": 5}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        fw._client = mock_client

        result = fw.dispatch_action("Lung", "start", "5")
        assert result["ok"] is True
        assert "reciprocate" in result["detail"]

    def test_dispatch_lung_stop(self):
        fw = FirmwareAdapter.__new__(FirmwareAdapter)
        fw.base_url = "http://localhost:8202"
        fw.timeout = 5.0
        fw._client = None

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "status": "stopped"}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        fw._client = mock_client

        result = fw.dispatch_action("Lung", "stop", "")
        assert result["ok"] is True
        assert "stop" in result["detail"].lower()

    def test_set_peripheral_lung_start(self):
        fw = FirmwareAdapter.__new__(FirmwareAdapter)
        fw.base_url = "http://localhost:8202"
        fw.timeout = 5.0

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        fw._client = mock_client

        fw.set_peripheral("lung", 5)
        # Should call POST /api/v1/hardware/lung with cycles
        calls = [c for c in mock_client.post.call_args_list if "/lung" in str(c)]
        assert len(calls) >= 1

    def test_set_peripheral_lung_stop(self):
        fw = FirmwareAdapter.__new__(FirmwareAdapter)
        fw.base_url = "http://localhost:8202"
        fw.timeout = 5.0

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        fw._client = mock_client

        fw.set_peripheral("lung", 0)
        # Should call POST /api/v1/hardware/lung/stop
        calls = [c for c in mock_client.post.call_args_list if "/lung/stop" in str(c)]
        assert len(calls) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 4 — HardwareGateway mock mode
# ═══════════════════════════════════════════════════════════════════════════════


class TestHardwareGatewayLung:
    def test_set_lung_mock(self):
        gw = HardwareGateway(mode="mock")
        result = asyncio.run(gw.set_lung(steps=500, speed=10_000_000, cycles=5, pause=0.5))
        assert result is True

    def test_stop_lung_mock(self):
        gw = HardwareGateway(mode="mock")
        result = asyncio.run(gw.stop_lung())
        assert result is True


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 5 — CQL interpreter dry-run with lung
# ═══════════════════════════════════════════════════════════════════════════════


class TestCqlInterpreterLung:
    def test_dry_run_lung_action(self):
        from oqlos.core.interpreter import CqlInterpreter
        from oqlos.core.base import StepStatus

        src = """SCENARIO: Lung test
GOAL: Reciprocate lung
  1. Start lung:
     → Lung.start 5
  2. Stop lung:
     → Lung.stop
"""
        interp = CqlInterpreter(mode="dry-run", quiet=True)
        result = interp.run(src)
        assert result.ok is True
        assert len(result.steps) == 2
        assert all(s.status == StepStatus.PASSED for s in result.steps)
