# firmware/models/scenarios.py
from typing import Any
from pydantic import BaseModel

class Step(BaseModel):
    id: str
    action: str
    label: str | None = None
    peripheral: str | None = None
    value: Any = None
    duration: int | None = None  # milliseconds
    condition: str | None = None

class ValidationRule(BaseModel):
    peripheral: str
    condition: str
    errorMessage: str

class Goal(BaseModel):
    id: str
    name: str
    description: str
    steps: list[Step]
    expectedResult: str
    validationCriteria: list[ValidationRule]

class Scenario(BaseModel):
    id: str
    name: str
    description: str
    device: str
    protocol: str
    code: str | None = None
    slug: str | None = None
    goals: list[Goal]
