"""Runtime AST dataclasses for parsed OQL documents.

The ``Cql*`` class names remain compatibility symbols. New integrations should
use the ``Oql*`` aliases exported at the end of this module.
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
    pass_message: str = ""     # Message shown when CHECK passes

@dataclass
class CqlAction:
    """An action within a step: → Target.method args, TASK, SET, WAIT, or PUMP."""
    kind: str = "action"     # action, task, set, pump, save, wait, condition, min, max, val, if_else
    target: str = ""
    method: str = ""
    args: str = ""
    condition: CqlCondition | None = None
    raw: str = ""
    then_actions: list[CqlAction] = field(default_factory=list)
    else_actions: list[CqlAction] = field(default_factory=list)
    loop_actions: list[CqlAction] = field(default_factory=list)

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
    """Internal runtime AST node for an OQL document."""
    filename: str = ""
    metadata: CqlMetadata = field(default_factory=CqlMetadata)
    intervals: list[CqlInterval] = field(default_factory=list)
    scenarios: list[CqlScenario] = field(default_factory=list)
    # Simple-format goals (GOAL: blocks without @Scenario wrapper)
    goals: list[CqlGoal] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# Canonical public names; legacy class names remain ABI-compatible aliases.
OqlMetadata = CqlMetadata
OqlInterval = CqlInterval
OqlCondition = CqlCondition
OqlAction = CqlAction
OqlStep = CqlStep
OqlGoal = CqlGoal
OqlScenario = CqlScenario
OqlDocument = CqlDocument
