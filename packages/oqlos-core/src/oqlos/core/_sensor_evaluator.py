"""
Sensor evaluation and condition checking for the OQL interpreter.

Handles sensor value comparison, auto-mocking, and condition evaluation.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from oqlos.models.dsl_models import CqlAction, CqlCondition, CqlDocument
    from oqlos.core.base import StepStatus


class SensorEvaluator:
    """Evaluates sensor conditions and manages sensor values."""

    # Default mock sensor values for realistic dry-run simulation
    DEFAULT_MOCK_SENSORS: dict[str, float] = {
        "AI01": -12.0,   # NC pressure sensor (mbar) — typical negative pressure
        "AI02": 7.0,     # SC pressure sensor (bar) — typical medium pressure
        "AI03": 290.0,   # WC pressure sensor (bar) — typical bottle pressure
    }

    # Operator → (needs_nudge_down, comparison_fn) for scalar operators
    _SCALAR_OPS: dict[str, tuple[bool, Any]] = {
        "≤":  (True,  lambda v, t: v <= t),
        "<=": (True,  lambda v, t: v <= t),
        "<":  (True,  lambda v, t: v < t),
        "≥":  (False, lambda v, t: v >= t),
        ">=": (False, lambda v, t: v >= t),
        ">":  (False, lambda v, t: v > t),
        "=":  (False, lambda v, t: v == t),
        "==": (False, lambda v, t: v == t),
        "!=": (False, lambda v, t: v != t),
    }

    # Operator → seed value factory for seed_sensors_from_conditions
    _SEED_VALUE_FNS: dict[str, Any] = {
        "≤":  lambda v: v * 0.5,
        "<=": lambda v: v * 0.5,
        "<":  lambda v: v - 1.0,
        "≥":  lambda v: v * 1.5 if v > 0 else v * 0.5,
        ">=": lambda v: v * 1.5 if v > 0 else v * 0.5,
        ">":  lambda v: v + 1.0,
        "=":  lambda v: v,
        "==": lambda v: v,
        "!=": lambda v: v + 1.0 if v >= 0 else v - 1.0,
    }

    def __init__(
        self,
        sensor_values: dict[str, float] | None = None,
        auto_mock: bool = False,
        mode: str = "dry-run",
    ):
        """
        Initialize sensor evaluator.

        Args:
            sensor_values: Initial sensor values to overlay on defaults
            auto_mock: Whether to auto-mock sensor values in dry-run mode
            mode: Execution mode (validate, dry-run, execute)
        """
        self.mode = mode
        self._auto_mock = auto_mock and mode == "dry-run"
        # Seed with defaults only outside real execution. In execute mode a
        # missing sensor read must remain visible instead of silently becoming a
        # mock value.
        self.sensor_values: dict[str, float] = (
            {} if mode == "execute" else dict(self.DEFAULT_MOCK_SENSORS)
        )
        if sensor_values:
            self.sensor_values.update(sensor_values)

    @staticmethod
    def collect_sensor_constraints(
        doc: "CqlDocument",
    ) -> dict[str, list[tuple[str, float | None, float | None]]]:
        """Walk AST and collect per-sensor condition constraints."""
        all_goals = list(doc.goals)
        for sc in doc.scenarios:
            all_goals.extend(sc.goals)

        sensor_ranges: dict[str, list[tuple[str, float | None, float | None]]] = {}
        for goal in all_goals:
            for step in goal.steps:
                for act in step.actions:
                    cond = act.condition
                    if not cond or not cond.sensor or cond.sensor == "Timer":
                        continue
                    sensor = cond.sensor[1:] if cond.sensor.startswith("Δ") else cond.sensor
                    sensor_ranges.setdefault(sensor, []).append((
                        cond.operator,
                        cond.value_min if cond.value_min is not None else cond.value,
                        cond.value_max,
                    ))
        return sensor_ranges

    def seed_sensors_from_conditions(self, doc: "CqlDocument") -> None:
        """Analyze conditions in document and seed mid-range sensor values for dry-run."""
        sensor_ranges = self.collect_sensor_constraints(doc)

        for sensor, constraints in sensor_ranges.items():
            if sensor in self.sensor_values and sensor not in self.DEFAULT_MOCK_SENSORS:
                continue  # User already provided a value
            for op, vmin, vmax in constraints:
                if op == "∈" and vmin is not None and vmax is not None:
                    self.sensor_values[sensor] = (vmin + vmax) / 2.0
                    break
                seed_fn = self._SEED_VALUE_FNS.get(op)
                if seed_fn and vmin is not None:
                    self.sensor_values[sensor] = seed_fn(vmin)
                    break

    def auto_mock_sensor(self, sensor: str, cond: "CqlCondition", val: float) -> float:
        """In dry-run auto-mock, nudge sensor value to satisfy condition."""
        if cond.operator == "∈" and cond.value_min is not None and cond.value_max is not None:
            val = (cond.value_min + cond.value_max) / 2.0
        elif cond.operator in self._SCALAR_OPS and cond.value is not None:
            nudge_down, cmp_fn = self._SCALAR_OPS[cond.operator]
            if not cmp_fn(val, cond.value):
                offset = abs(cond.value) * 0.1 + 0.1
                val = cond.value - offset if nudge_down else cond.value + offset
        self.sensor_values[sensor] = val
        return val

    def compare_sensor(
        self,
        sensor: str,
        cond: "CqlCondition",
        val: float,
    ) -> tuple[bool, str]:
        """Compare sensor value against condition. Returns (ok, description)."""
        if cond.operator == "∈" and cond.value_min is not None and cond.value_max is not None:
            ok = cond.value_min <= val <= cond.value_max
            return ok, f"{sensor} = {val} ∈ [{cond.value_min}, {cond.value_max}] {cond.unit}"
        if cond.operator in self._SCALAR_OPS:
            _, cmp_fn = self._SCALAR_OPS[cond.operator]
            ok = cmp_fn(val, cond.value or 0)
            return ok, f"{sensor} = {val} {cond.operator} {cond.value} {cond.unit}"
        return True, f"{sensor} {cond.operator} {cond.value} {cond.unit}"

    def get_sensor_value(self, sensor: str) -> float | None:
        """Get current sensor value, handling delta sensors."""
        # Delta sensors (ΔAI02) — use base sensor name for lookup
        base_sensor = sensor[1:] if sensor.startswith("Δ") else sensor
        return self.sensor_values.get(sensor, self.sensor_values.get(base_sensor))
