"""Shared dependency injection and execution control helpers.

Centralises the state_manager / orchestrator globals that were previously
duplicated across execution.py, state.py, peripherals.py, and scenarios.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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


def get_state_manager() -> StateManager:
    """Return state_manager, raising if not initialised."""
    if state_manager is None:
        raise RuntimeError("state_manager not initialised — call set_dependencies() first")
    return state_manager


def get_orchestrator() -> ScenarioOrchestrator:
    """Return orchestrator, raising if not initialised."""
    if orchestrator is None:
        raise RuntimeError("orchestrator not initialised — call set_dependencies() first")
    return orchestrator


# ── Pause / resume / stop ────────────────────────────────────────

def do_pause(execution_id: str | None = None) -> dict:
    """Core pause logic shared by REST + command bus handlers."""
    sm = get_state_manager()
    orch = get_orchestrator()
    orch.paused = True
    if execution_id and execution_id in sm.executions:
        sm.executions[execution_id].status = "paused"
    elif orch.current_execution:
        orch.current_execution.status = "paused"
    return {"status": "paused"}


def do_resume(execution_id: str | None = None) -> dict:
    """Core resume logic shared by REST + command bus handlers."""
    sm = get_state_manager()
    orch = get_orchestrator()
    orch.paused = False
    if execution_id and execution_id in sm.executions:
        sm.executions[execution_id].status = "running"
    elif orch.current_execution:
        orch.current_execution.status = "running"
    return {"status": "running"}


def do_stop(execution_id: str | None = None) -> dict:
    """Core stop logic shared by REST + command bus handlers."""
    sm = get_state_manager()
    orch = get_orchestrator()
    orch.running = False
    if execution_id and execution_id in sm.executions:
        sm.executions[execution_id].status = "stopped"
    elif orch.current_execution:
        orch.current_execution.status = "stopped"
    return {"status": "stopped"}
