# firmware/models/execution.py
from typing import Any
from pydantic import BaseModel, ConfigDict

class ExecutionRequest(BaseModel):
    scenarioId: str
    goals: list[str] | None = None
    mode: str = 'auto'
    speed: float = 1.0
    content: dict[str, Any] | None = None  # DSL content from frontend

class ExecutionStatus(BaseModel):
    """Event-sourced: only oqlos.core.cqrs.execution may produce a new instance
    (via model_copy in ExecutionAggregate.apply). Frozen so any code that tries
    to mutate a field directly — bypassing the CommandBus — fails loudly."""

    model_config = ConfigDict(frozen=True)

    executionId: str
    scenarioId: str
    status: str
    currentGoal: str | None = None
    currentStep: str | None = None
    progress: float = 0.0

class CommandEnvelope(BaseModel):
    command: str
    data: dict[str, Any] | None = None
