"""Shared dependency injection and execution control helpers.

Centralises the state_manager / orchestrator globals that were previously
duplicated across execution.py, state.py, peripherals.py, and scenarios.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from oqlos.core.cqrs.execution import SetExecutionStatusCommand
from oqlos.errors import OqlosError

if TYPE_CHECKING:
    from oqlos.core.state import StateManager
    from oqlos.core.executor import ScenarioOrchestrator

# ── Shared globals ────────────────────────────────────────────────

state_manager: StateManager | None = None
orchestrator: ScenarioOrchestrator | None = None


def set_dependencies(sm: StateManager, orch: ScenarioOrchestrator) -> None:
    """Set state_manager + orchestrator (called once from main.py)."""
    global state_manager, orchestrator
    state_manager = sm
    orchestrator = orch


def _make_getter(name: str, label: str):
    """Factory for state_manager / orchestrator getters."""
    def getter():
        val = globals().get(name)
        if val is None:
            raise OqlosError(
                code="api_execution_runtime_unavailable",
                status_code=503,
                detail={
                    "architecture": "SOA",
                    "layer": "oqlos",
                    "component": "scenario-execution",
                    "stage": "dependency.resolve",
                    "problem_source": "runtime-state",
                    "operation_id": "execution.dependencies.resolve",
                    "upstream_target": "runtime://scenario-execution",
                    "dependency": label,
                },
            )
        return val
    getter.__name__ = f"get_{label}"
    return getter


get_state_manager = _make_getter("state_manager", "state_manager")
get_orchestrator = _make_getter("orchestrator", "orchestrator")


# ── Pause / resume / stop ────────────────────────────────────────

def _make_exec_handler(orch_attr: str, orch_value: bool, target_status: str):
    """Factory for pause/resume/stop — eliminates 3 near-identical functions."""
    def handler(execution_id: str | None = None) -> dict:
        sm = get_state_manager()
        orch = get_orchestrator()
        setattr(orch, orch_attr, orch_value)
        target_id = execution_id if execution_id and execution_id in sm.executions else (
            orch.current_execution.executionId if orch.current_execution else None
        )
        if target_id:
            sm.command_bus.dispatch(SetExecutionStatusCommand(execution_id=target_id, status=target_status))
        return {"status": target_status}
    handler.__name__ = f"do_{target_status}"
    return handler


do_pause = _make_exec_handler("paused", True, "paused")
do_resume = _make_exec_handler("paused", False, "running")
do_stop = _make_exec_handler("running", False, "stopped")
