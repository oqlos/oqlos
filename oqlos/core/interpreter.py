"""
CQL Interpreter — executes parsed CQL scenarios.

Modes:
  - validate: parse + check structure (no execution)
  - dry-run:  walk through steps, simulate sensor values
  - execute:  connect to hardware/API and run real test
"""

from __future__ import annotations

import time
from typing import Any

from oqlos.core.base import (
    BaseInterpreter,
    ScriptResult,
    StepResult,
    StepStatus,
)
from oqlos.models.dsl_models import CqlAction, CqlCondition, CqlDocument, CqlGoal, CqlStep
from oqlos.core.cql_parser import parse_cql, validate_cql


class CqlInterpreter(BaseInterpreter):
    """
    CQL interpreter with three modes:
      - validate: parse + check structure
      - dry-run:  simulate execution with mock sensor values
      - execute:  connect to firmware simulator (:8202) and run real test
    """

    # Default mock sensor values for realistic dry-run simulation
    DEFAULT_MOCK_SENSORS: dict[str, float] = {
        "AI01": -12.0,   # NC pressure sensor (mbar) — typical negative pressure
        "AI02": 7.0,     # SC pressure sensor (bar) — typical medium pressure
        "AI03": 290.0,   # WC pressure sensor (bar) — typical bottle pressure
    }

    def __init__(
        self,
        mode: str = "dry-run",
        variables: dict[str, Any] | None = None,
        quiet: bool = False,
        sensor_values: dict[str, float] | None = None,
        firmware_url: str = "http://localhost:8202",
        auto_mock: bool = True,
        skip_waits: bool = False,
    ):
        super().__init__(variables=variables, quiet=quiet)
        self.mode = mode  # validate, dry-run, execute
        self._firmware = None
        self._firmware_url = firmware_url
        self._skip_waits = skip_waits
        self._auto_mock = auto_mock and mode == "dry-run"
        # Seed with defaults, then overlay user-provided values
        self.sensor_values: dict[str, float] = dict(self.DEFAULT_MOCK_SENSORS)
        if sensor_values:
            self.sensor_values.update(sensor_values)

    def parse(self, source: str, filename: str = "<string>") -> CqlDocument:
        return parse_cql(source, filename)

    def _print_header(self, doc: CqlDocument, name: str) -> None:
        """Print execution header with metadata."""
        self.out.step("📋", f"CQL: {name}")
        if doc.metadata.device_type:
            self.out.step("🔧", f"Device: {doc.metadata.device_type} / {doc.metadata.device_model}")
        if doc.intervals:
            self.out.step("⏱️ ", f"Intervals: {len(doc.intervals)}")

    def _collect_warnings(self, doc: CqlDocument, issues: list[str]) -> None:
        """Collect and emit warnings from document and validation issues."""
        for w in doc.warnings:
            self.warnings.append(w)
            self.out.warn(w)
        for issue in issues:
            self.warnings.append(issue)
            self.out.warn(issue)

    def _run_validation_mode(self, name: str, issues: list[str], t0: float) -> ScriptResult:
        """Return early result for validate mode."""
        ok = len(issues) == 0
        return ScriptResult(
            source=name, ok=ok, steps=self.results,
            variables=self.vars.all(), errors=self.errors,
            warnings=self.warnings, duration_ms=(time.monotonic() - t0) * 1000,
        )

    def _collect_all_goals(self, doc: CqlDocument) -> list[tuple[str, CqlGoal]]:
        """Collect all goals from document and scenarios."""
        all_goals: list[tuple[str, CqlGoal]] = []
        for g in doc.goals:
            all_goals.append(("", g))
        for sc in doc.scenarios:
            for g in sc.goals:
                all_goals.append((sc.name, g))
        return all_goals

    def _execute_single_goal(self, sc_name: str, goal: CqlGoal) -> None:
        """Execute all steps in a single goal."""
        prefix = f"{sc_name}/" if sc_name else ""
        self.out.step("🎯", f"GOAL: {prefix}{goal.name}")
        if goal.description:
            self.out.info(f"  {goal.description}")

        for step in goal.steps:
            result = self._execute_step(step, goal)
            self.results.append(result)

    def _execute_all_goals(self, all_goals: list[tuple[str, CqlGoal]]) -> None:
        """Execute all collected goals."""
        for sc_name, goal in all_goals:
            self._execute_single_goal(sc_name, goal)

    def _build_script_result(self, name: str, t0: float) -> ScriptResult:
        """Build final script execution result."""
        elapsed = (time.monotonic() - t0) * 1000
        ok = all(r.status in (StepStatus.PASSED, StepStatus.SKIPPED) for r in self.results)
        sr = ScriptResult(
            source=name, ok=ok, steps=self.results,
            variables=self.vars.all(), errors=self.errors,
            warnings=self.warnings, duration_ms=elapsed,
        )
        self.out.emit("")
        self.out.emit(sr.summary())
        return sr

    def execute(self, parsed: CqlDocument) -> ScriptResult:
        """Execute CQL document through all phases: header, validate, execute, result."""
        doc = parsed
        t0 = time.monotonic()
        name = doc.metadata.scenario_name or doc.filename

        self._print_header(doc, name)

        issues = validate_cql(doc)
        self._collect_warnings(doc, issues)

        if self.mode == "validate":
            return self._run_validation_mode(name, issues, t0)

        if self._auto_mock:
            self._seed_sensors_from_conditions(doc)

        all_goals = self._collect_all_goals(doc)
        self._execute_all_goals(all_goals)

        return self._build_script_result(name, t0)

    def _execute_step(self, step: CqlStep, goal: CqlGoal) -> StepResult:
        t0 = time.monotonic()
        self.out.step("  📌", f"Step {step.number}: {step.name}")
        status = StepStatus.PASSED
        details: dict[str, Any] = {}
        message = ""

        for act in step.actions:
            act_result = self._execute_action(act)
            if act_result == StepStatus.FAILED:
                status = StepStatus.FAILED
                message = act.raw
            elif act_result == StepStatus.ERROR:
                status = StepStatus.ERROR
                message = act.raw

        elapsed = (time.monotonic() - t0) * 1000
        icon = {"passed": "✅", "failed": "❌", "error": "💥"}.get(status.value, "⏭️")
        self.out.step(f"    {icon}", f"[{status.value}] {step.name}")

        return StepResult(
            name=f"{step.number}. {step.name}",
            status=status, message=message,
            duration_ms=elapsed, details=details,
        )

    def _execute_action(self, act: CqlAction) -> StepStatus:
        """Dispatch a CQL action to the appropriate handler."""
    # ── Action dispatch table ───────────────────────────────────────

    def _exec_action_action(self, act: CqlAction) -> StepStatus:
        if self.mode == "execute":
            return self._execute_firmware_action(act)
        self.out.step("    →", f"{act.target}.{act.method} {act.args}")
        return StepStatus.PASSED

    def _exec_action_task(self, act: CqlAction) -> StepStatus:
        self.out.step("    🔨", act.args)
        return StepStatus.PASSED

    def _exec_action_set(self, act: CqlAction) -> StepStatus:
        value = (act.args or "").strip()
        target_lower = (act.target or "").strip().lower()
        self.vars.set(act.target, value)

        if target_lower in {"wait", "delay", "pause", "timeout"}:
            return self._exec_set_wait(act, value)

        if self.mode == "execute":
            if any(token in target_lower for token in ("zawór", "zawor", "valve", "pompa", "pump", "sprężarka", "sprezarka", "compressor")):
                result = self._exec_set_peripheral(act, value)
                if result is not None:
                    return result
        self.out.step("    ⚙️", f"SET [{act.target}] = [{value}]")
        return StepStatus.PASSED

    def _exec_set_wait(self, act: CqlAction, value: str) -> StepStatus:
        secs = self._parse_wait_secs(value)
        if self.mode == "dry-run":
            self.out.step("    ⏳", f"SET [{act.target}] = [{value}] (simulated)")
        elif self._skip_waits:
            self.out.step("    ⏳", f"SET [{act.target}] = [{value}] (skipped)")
        else:
            self._do_sleep(secs, f"SET [{act.target}] = [{value}]")
        return StepStatus.PASSED

    def _exec_set_peripheral(self, act: CqlAction, value: str) -> StepStatus | None:
        fw = self._get_firmware()
        normalized_value: Any = value
        lowered = value.lower()
        if lowered in {"on", "true"}:
            normalized_value = 1
        elif lowered in {"off", "false"}:
            normalized_value = 0
        else:
            try:
                import re as _re
                match = _re.search(r"[-+]?\d*\.?\d+", value.replace(",", "."))
                if match:
                    num = float(match.group(0))
                    normalized_value = int(num) if num.is_integer() else num
            except Exception:
                normalized_value = value
        try:
            fw.set_peripheral(act.target or "", normalized_value)
        except Exception as exc:
            self.errors.append(str(exc))
            self.out.error(str(exc))
            return StepStatus.ERROR
        return None

    def _exec_action_save(self, act: CqlAction) -> StepStatus:
        val = self.sensor_values.get(act.target, 0.0) if act.target.startswith("AI") else "OK"
        self.vars.set(act.target, val)
        self.out.step("    💾", f"SAVE {act.target} = {val}")
        return StepStatus.PASSED

    @staticmethod
    def _parse_wait_secs(raw: str) -> float:
        """Parse a WAIT value to seconds.  Default unit is ms."""
        import re as _re
        low = raw.lower().strip()
        match = _re.search(r"[-+]?\d*\.?\d+", low.replace(",", "."))
        if not match:
            return 0.0
        num = float(match.group(0))
        if "s" in low and "ms" not in low:
            return num  # explicit seconds
        # bare number or explicit "ms" → milliseconds
        return num / 1000.0

    def _exec_action_wait(self, act: CqlAction) -> StepStatus:
        secs = self._parse_wait_secs(act.args)
        if self.mode == "dry-run":
            self.out.step("    ⏳", f"WAIT {secs}s (simulated)")
        elif self._skip_waits:
            self.out.step("    ⏳", f"WAIT {secs}s (skipped)")
        else:
            self._do_sleep(secs, f"WAIT {secs}s")
        return StepStatus.PASSED

    def _exec_action_min_max(self, act: CqlAction) -> StepStatus:
        self.out.step("    📏", f"{act.kind.upper()} [{act.target}] = {act.args}")
        return StepStatus.PASSED

    def _exec_action_val(self, act: CqlAction) -> StepStatus:
        sensor = act.target
        val = self.sensor_values.get(sensor, 0.0)
        self.vars.set(sensor, val)
        self.out.step("    📊", f"VAL [{sensor}] = {val} {act.args}")
        return StepStatus.PASSED

    def _exec_action_condition(self, act: CqlAction) -> StepStatus:
        if self.mode == "execute":
            self._refresh_sensors_from_firmware()
        return self._evaluate_condition(act)

    def _do_sleep(self, secs: float, label: str) -> None:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self.out.step("    ⏳", f"{label} (skipped in sync)")
            else:
                loop.run_until_complete(asyncio.sleep(max(secs, 0.0)))
                self.out.step("    ⏳", label)
        except RuntimeError:
            time.sleep(max(secs, 0.0))
            self.out.step("    ⏳", label)

    _ACTION_DISPATCH: dict[str, str] = {
        "action": "_exec_action_action",
        "task": "_exec_action_task",
        "set": "_exec_action_set",
        "save": "_exec_action_save",
        "wait": "_exec_action_wait",
        "min": "_exec_action_min_max",
        "max": "_exec_action_min_max",
        "val": "_exec_action_val",
        "condition": "_exec_action_condition",
        "if_else": "_exec_action_condition",
    }

    def _execute_action(self, act: CqlAction) -> StepStatus:
        method_name = self._ACTION_DISPATCH.get(act.kind)
        if method_name is not None:
            return getattr(self, method_name)(act)
        return StepStatus.PASSED

    # Operator → seed value factory for _seed_sensors_from_conditions
    _SEED_VALUE_FNS: dict[str, Any] = {
        "≤":  lambda v: v * 0.5,
        "<=": lambda v: v * 0.5,
        "<":  lambda v: v - 1.0,
        "≥":  lambda v: v * 1.5 if v > 0 else v * 0.5,
        ">=": lambda v: v * 1.5 if v > 0 else v * 0.5,
        ">":  lambda v: v + 1.0,
    }

    @staticmethod
    def _collect_sensor_constraints(doc: CqlDocument) -> dict[str, list[tuple[str, float | None, float | None]]]:
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

    def _seed_sensors_from_conditions(self, doc: CqlDocument) -> None:
        """Analyze conditions in document and seed mid-range sensor values for dry-run."""
        sensor_ranges = self._collect_sensor_constraints(doc)

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

    def _get_firmware(self):
        """Lazy-init firmware adapter."""
        if self._firmware is None:
            try:
                from oqlos.hardware.firmware_adapter import FirmwareAdapter
            except ImportError:
                raise RuntimeError(
                    "FirmwareAdapter not available — install oqlos with firmware extras "
                    "or run inside the c2004 monorepo"
                )
            self._firmware = FirmwareAdapter(base_url=self._firmware_url)
        return self._firmware

    def _execute_firmware_action(self, act: CqlAction) -> StepStatus:
        """Dispatch action to firmware simulator via HTTP."""
        fw = self._get_firmware()
        result = fw.dispatch_action(act.target, act.method, act.args)
        if result["ok"]:
            self.out.step("    → 🔧", f"{act.target}.{act.method} → {result['detail']}")
            return StepStatus.PASSED
        else:
            self.out.step("    → ❌", f"{act.target}.{act.method} FAILED: {result['detail']}")
            self.errors.append(result["detail"])
            return StepStatus.ERROR

    def _refresh_sensors_from_firmware(self) -> None:
        """Read all sensor values from firmware and update local cache."""
        try:
            fw = self._get_firmware()
            readings = fw.read_all_sensors()
            self.sensor_values.update(readings)
        except Exception:
            pass  # Keep existing mock values on failure

    # Operator → (needs_nudge_down, comparison_fn) for scalar operators
    _SCALAR_OPS: dict[str, tuple[bool, Any]] = {
        "≤":  (True,  lambda v, t: v <= t),
        "<=": (True,  lambda v, t: v <= t),
        "<":  (True,  lambda v, t: v < t),
        "≥":  (False, lambda v, t: v >= t),
        ">=": (False, lambda v, t: v >= t),
        ">":  (False, lambda v, t: v > t),
    }

    def _auto_mock_sensor(self, sensor: str, cond: CqlCondition, val: float) -> float:
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

    def _compare_sensor(self, sensor: str, cond: CqlCondition, val: float) -> tuple[bool, str]:
        """Compare sensor value against condition. Returns (ok, description)."""
        if cond.operator == "∈" and cond.value_min is not None and cond.value_max is not None:
            ok = cond.value_min <= val <= cond.value_max
            return ok, f"{sensor} = {val} ∈ [{cond.value_min}, {cond.value_max}] {cond.unit}"
        if cond.operator in self._SCALAR_OPS:
            _, cmp_fn = self._SCALAR_OPS[cond.operator]
            ok = cmp_fn(val, cond.value or 0)
            return ok, f"{sensor} = {val} {cond.operator} {cond.value} {cond.unit}"
        return True, f"{sensor} {cond.operator} {cond.value} {cond.unit}"

    def _evaluate_condition(self, act: CqlAction) -> StepStatus:
        cond = act.condition
        if not cond:
            return StepStatus.PASSED

        sensor = cond.sensor
        # Timer conditions: always pass in dry-run
        if sensor == "Timer":
            self.out.step("    ⏱️ ", f"Timer {cond.operator} {cond.value}s → OK (simulated)")
            return StepStatus.PASSED

        # Delta sensors (ΔAI02) — use base sensor name for lookup
        base_sensor = sensor[1:] if sensor.startswith("Δ") else sensor
        val = self.sensor_values.get(sensor, self.sensor_values.get(base_sensor, 0.0))

        if self._auto_mock and self.mode == "dry-run":
            val = self._auto_mock_sensor(sensor, cond, val)

        ok, desc = self._compare_sensor(sensor, cond, val)

        if ok:
            self.out.step("    ✅", f"{desc} → PASS")
            return StepStatus.PASSED
        else:
            self.out.step("    ❌", f"{desc} → {cond.on_fail}: {cond.fail_message}")
            if cond.on_fail == "ERROR":
                self.errors.append(f"{sensor}: {cond.fail_message}")
                return StepStatus.FAILED
            return StepStatus.WARNING
