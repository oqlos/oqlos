"""Event-sourced ExecutionStatus aggregate for scenario/goal/step lifecycle tracking.

StateManager.executions is a Projection folded from this stream — nothing
outside this module writes to an ExecutionStatus's fields directly.
"""

from __future__ import annotations

from dataclasses import dataclass

from oqlos.models.execution import ExecutionStatus

from .aggregate import Aggregate
from .commands import Command
from .events import Event
from .projection import Projection

# --- Events ------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class ExecutionStarted(Event):
    scenario_id: str


@dataclass(frozen=True, kw_only=True)
class ExecutionGoalStarted(Event):
    goal_id: str


@dataclass(frozen=True, kw_only=True)
class ExecutionStepStarted(Event):
    step_id: str


@dataclass(frozen=True, kw_only=True)
class ExecutionProgressUpdated(Event):
    progress: float


@dataclass(frozen=True, kw_only=True)
class ExecutionStatusChanged(Event):
    status: str


# --- Aggregate -----------------------------------------------------------------


class ExecutionAggregate(Aggregate):
    """Rehydrates a single execution's current shape by replaying its event stream."""

    def __init__(self, aggregate_id: str) -> None:
        super().__init__(aggregate_id)
        self.execution: ExecutionStatus | None = None

    def apply(self, event: Event) -> None:
        if isinstance(event, ExecutionStarted):
            self.execution = ExecutionStatus(
                executionId=self.aggregate_id,
                scenarioId=event.scenario_id,
                status="running",
                currentGoal=None,
                currentStep=None,
                progress=0.0,
            )
        elif self.execution is None:
            return  # Ignore events for an execution that was never started.
        elif isinstance(event, ExecutionGoalStarted):
            self.execution = self.execution.model_copy(update={"currentGoal": event.goal_id})
        elif isinstance(event, ExecutionStepStarted):
            self.execution = self.execution.model_copy(update={"currentStep": event.step_id})
        elif isinstance(event, ExecutionProgressUpdated):
            self.execution = self.execution.model_copy(update={"progress": event.progress})
        elif isinstance(event, ExecutionStatusChanged):
            self.execution = self.execution.model_copy(update={"status": event.status})


# --- Commands --------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class StartExecutionCommand(Command):
    execution_id: str
    scenario_id: str


@dataclass(frozen=True, kw_only=True)
class StartGoalCommand(Command):
    execution_id: str
    goal_id: str


@dataclass(frozen=True, kw_only=True)
class StartStepCommand(Command):
    execution_id: str
    step_id: str


@dataclass(frozen=True, kw_only=True)
class UpdateProgressCommand(Command):
    execution_id: str
    progress: float


@dataclass(frozen=True, kw_only=True)
class SetExecutionStatusCommand(Command):
    execution_id: str
    status: str


def handle_start_execution(cmd: StartExecutionCommand) -> list[Event]:
    return [ExecutionStarted(stream_id=cmd.execution_id, scenario_id=cmd.scenario_id)]


def handle_start_goal(cmd: StartGoalCommand) -> list[Event]:
    return [ExecutionGoalStarted(stream_id=cmd.execution_id, goal_id=cmd.goal_id)]


def handle_start_step(cmd: StartStepCommand) -> list[Event]:
    return [ExecutionStepStarted(stream_id=cmd.execution_id, step_id=cmd.step_id)]


def handle_update_progress(cmd: UpdateProgressCommand) -> list[Event]:
    return [ExecutionProgressUpdated(stream_id=cmd.execution_id, progress=cmd.progress)]


def handle_set_execution_status(cmd: SetExecutionStatusCommand) -> list[Event]:
    return [ExecutionStatusChanged(stream_id=cmd.execution_id, status=cmd.status)]


EXECUTION_HANDLERS: dict[type[Command], object] = {
    StartExecutionCommand: handle_start_execution,
    StartGoalCommand: handle_start_goal,
    StartStepCommand: handle_start_step,
    UpdateProgressCommand: handle_update_progress,
    SetExecutionStatusCommand: handle_set_execution_status,
}


# --- Projection (read model) ------------------------------------------------


class ExecutionsProjection(Projection):
    """Read model: `executions[id]` mirrors the latest replayed state of each stream."""

    def __init__(self) -> None:
        self.executions: dict[str, ExecutionStatus] = {}
        self._aggregates: dict[str, ExecutionAggregate] = {}

    def apply(self, event: Event) -> None:
        if not isinstance(
            event,
            (
                ExecutionStarted,
                ExecutionGoalStarted,
                ExecutionStepStarted,
                ExecutionProgressUpdated,
                ExecutionStatusChanged,
            ),
        ):
            return
        aggregate = self._aggregates.setdefault(event.stream_id, ExecutionAggregate(event.stream_id))
        aggregate.apply(event)
        if aggregate.execution is not None:
            self.executions[event.stream_id] = aggregate.execution
