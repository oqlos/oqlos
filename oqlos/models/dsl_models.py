"""
CQL AST node dataclasses.

Represents the parsed structure of a .cql scenario file.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CqlMetadata:
    scenario_name: str = ""
    device_type: str = ""
    device_model: str = ""
    manufacturer: str = ""

@dataclass
class CqlInterval:
    code: str          # e.g. "tt#000"
    label: str         # e.g. "Po użyciu [M]"
    period_months: int = 0

@dataclass
class CqlCondition:
    """Sensor condition: AI01 ∈ [min, max] unit | ACTION 'msg'"""
    sensor: str = ""
    operator: str = ""       # ∈, ≤, ≥, <, >, =
    value: float | None = None
    value_min: float | None = None
    value_max: float | None = None
    unit: str = ""
    on_fail: str = ""        # ERROR, PASS, WAIT
    fail_message: str = ""

@dataclass
class CqlAction:
    """An action within a step: → Target.method args, TASK, SET, WAIT, or PUMP."""
    kind: str = "action"     # action, task, set, pump, save, wait, condition, min, max, val, if_else
    target: str = ""
    method: str = ""
    args: str = ""
    condition: CqlCondition | None = None
    raw: str = ""

@dataclass
class CqlStep:
    """A numbered step within a goal: 1. Step name:"""
    number: str = ""         # "1", "1.1", "2"
    name: str = ""
    description: str = ""
    actions: list[CqlAction] = field(default_factory=list)

@dataclass
class CqlGoal:
    """A test goal within a scenario."""
    name: str = ""
    description: str = ""
    editable: bool = False
    alarm: str = ""
    steps: list[CqlStep] = field(default_factory=list)

@dataclass
class CqlScenario:
    """A named scenario block: @Namespace.Name"""
    namespace: str = ""
    name: str = ""
    description: str = ""
    intervals: list[str] = field(default_factory=list)
    goals: list[CqlGoal] = field(default_factory=list)

@dataclass
class CqlDocument:
    """Root AST node for a .cql file."""
    filename: str = ""
    metadata: CqlMetadata = field(default_factory=CqlMetadata)
    intervals: list[CqlInterval] = field(default_factory=list)
    scenarios: list[CqlScenario] = field(default_factory=list)
    # Simple-format goals (GOAL: blocks without @Scenario wrapper)
    goals: list[CqlGoal] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
