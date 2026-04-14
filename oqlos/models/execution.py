# firmware/models/execution.py
from typing import Any
from pydantic import BaseModel

class ExecutionRequest(BaseModel):
    scenarioId: str
    goals: list[str] | None = None
    mode: str = 'auto'
    speed: float = 1.0
    content: dict[str, Any] | None = None  # DSL content from frontend

class ExecutionStatus(BaseModel):
    executionId: str
    scenarioId: str
    status: str
    currentGoal: str | None = None
    currentStep: str | None = None
    progress: float = 0.0

class CommandEnvelope(BaseModel):
    command: str
    data: dict[str, Any] | None = None
