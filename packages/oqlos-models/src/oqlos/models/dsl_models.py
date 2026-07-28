"""Runtime AST dataclasses for parsed OQL documents.

The ``Oql*`` classes are canonical. Historical ``Cql*`` names remain aliases
only for binary/import compatibility with older integrations.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OqlMetadata:
    scenario_name: str = ""
    device_type: str = ""
    device_model: str = ""
    manufacturer: str = ""

@dataclass
class OqlInterval:
    code: str          # e.g. "tt#000"
    label: str         # e.g. "Po użyciu [M]"
    period_months: int = 0

@dataclass
class OqlCondition:
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
class OqlAction:
    """An action within a step: → Target.method args, TASK, SET, WAIT, or PUMP."""
    kind: str = "action"     # action, task, set, pump, save, wait, condition, min, max, val, if_else
    target: str = ""
    method: str = ""
    args: str = ""
    condition: OqlCondition | None = None
    raw: str = ""
    then_actions: list[OqlAction] = field(default_factory=list)
    else_actions: list[OqlAction] = field(default_factory=list)
    loop_actions: list[OqlAction] = field(default_factory=list)

@dataclass
class OqlStep:
    """A numbered step within a goal: 1. Step name:"""
    number: str = ""         # "1", "1.1", "2"
    name: str = ""
    description: str = ""
    actions: list[OqlAction] = field(default_factory=list)

@dataclass
class OqlGoal:
    """A test goal within a scenario."""
    name: str = ""
    description: str = ""
    editable: bool = False
    alarm: str = ""
    steps: list[OqlStep] = field(default_factory=list)

@dataclass
class OqlScenario:
    """A named scenario block: @Namespace.Name"""
    namespace: str = ""
    name: str = ""
    description: str = ""
    intervals: list[str] = field(default_factory=list)
    goals: list[OqlGoal] = field(default_factory=list)

@dataclass
class OqlDocument:
    """Internal runtime AST node for an OQL document."""
    filename: str = ""
    metadata: OqlMetadata = field(default_factory=OqlMetadata)
    intervals: list[OqlInterval] = field(default_factory=list)
    scenarios: list[OqlScenario] = field(default_factory=list)
    # Simple-format goals (GOAL: blocks without @Scenario wrapper)
    goals: list[OqlGoal] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# Historical import names retained as ABI-compatible aliases.
CqlMetadata = OqlMetadata
CqlInterval = OqlInterval
CqlCondition = OqlCondition
CqlAction = OqlAction
CqlStep = OqlStep
CqlGoal = OqlGoal
CqlScenario = OqlScenario
CqlDocument = OqlDocument
