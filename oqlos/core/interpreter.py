"""
CQL Interpreter — executes parsed CQL scenarios.

Modes:
  - validate: parse + check structure (no execution)
  - dry-run:  walk through steps, simulate sensor values
  - execute:  connect to hardware/API and run real test

Refactored: Value normalization, sensor evaluation, and firmware execution
are now delegated to specialized modules:
  - _value_normalizers.ValueNormalizer
  - _sensor_evaluator.SensorEvaluator
  - _firmware_executor.FirmwareExecutor
"""

from __future__ import annotations

import re
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
from oqlos.core._value_normalizers import ValueNormalizer
from oqlos.core._sensor_evaluator import SensorEvaluator
from oqlos.core._firmware_executor import FirmwareExecutor


class CqlInterpreter(BaseInterpreter):
    """
    CQL interpreter with three modes:
      - validate: parse + check structure
      - dry-run:  simulate execution with mock sensor values
      - execute:  connect to firmware simulator (:8202) and run real test
    """

    def __init__(
        self,
        mode: str = "dry-run",
        variables: dict[str, Any] | None = None,
        quiet: bool = False,
        sensor_values: dict[str, float] | None = None,
        firmware_url: str = "http://localhost:8202",
        auto_mock: bool = True,
        skip_waits: bool = False,
        bridge_url: str | None = None,
        yaml_output: bool = False,
        use_plugin_gateway: bool = True,
    ):
        super().__init__(variables=variables, quiet=quiet, bridge_url=bridge_url)
        self.mode = mode  # validate, dry-run, execute
        self._skip_waits = skip_waits
        self._goal_skipped = False  # Track if current goal execution should be skipped (flat IF)
        self._loop_break = False  # Track REPEAT STOP inside loop bodies
        self._yaml_output = yaml_output

        # Initialize specialized components
        self._normalizer = ValueNormalizer(self.vars)
        self._sensor_eval = SensorEvaluator(
            sensor_values=sensor_values,
            auto_mock=auto_mock,
            mode=mode,
        )
        self._fw_exec = FirmwareExecutor(
            mode=mode,
            firmware_url=firmware_url,
            use_plugin_gateway=use_plugin_gateway,
            vars_store=self.vars,
            output_handler=self.out,
            normalizer=self._normalizer,
        )

    # --- Delegated properties for backward compatibility ---

    @property
    def sensor_values(self) -> dict[str, float]:
        """Access sensor values through the sensor evaluator."""
        return self._sensor_eval.sensor_values

    @sensor_values.setter
    def sensor_values(self, value: dict[str, float]) -> None:
        """Set sensor values through the sensor evaluator."""
        self._sensor_eval.sensor_values = value

    @property
    def _firmware(self):
        """Backward-compatible access to the delegated firmware adapter."""
        return self._fw_exec._firmware

    @_firmware.setter
    def _firmware(self, value) -> None:
        """Backward-compatible setter for tests and legacy code paths."""
        self._fw_exec._firmware = value

    @property
    def _firmware_url(self) -> str:
        """Backward-compatible access to the delegated firmware URL."""
        return self._fw_exec._firmware_url

    @_firmware_url.setter
    def _firmware_url(self, value: str) -> None:
        """Backward-compatible setter for tests and legacy code paths."""
        self._fw_exec._firmware_url = value

    def _coerce_float(self, value: Any) -> float | None:
        """Delegate to ValueNormalizer."""
        return self._normalizer.coerce_float(value)

    def _resolve_peripheral_id(self, target: str) -> str | None:
        """Delegate to FirmwareExecutor."""
        return self._fw_exec.resolve_peripheral_id(target)

    def _get_pump_flow_full_scale_lpm(self) -> float:
        """Delegate to ValueNormalizer."""
        return self._normalizer._get_pump_flow_full_scale_lpm()

    def _normalize_pump_power(self, raw_value: str) -> float:
        """Delegate to ValueNormalizer."""
        return self._normalizer.normalize_pump_power(raw_value)

    def _normalize_valve_value(self, raw_value: Any) -> bool:
        """Delegate to ValueNormalizer."""
        return self._normalizer.normalize_valve_value(raw_value)

    def _normalize_lung_value(self, raw_value: Any) -> int:
        """Delegate to ValueNormalizer."""
        return self._normalizer.normalize_lung_value(raw_value)

    def parse(self, source: str, filename: str = "<string>") -> CqlDocument:
        # Use the OQL parser for flat OQL files; some .oql examples contain
        # ConnectGo/CQL syntax and must stay on the CQL parser path.
        if filename.endswith('.oql'):
            from oqlos.core._oql_adapter import is_flat_oql, oql_doc_to_cql
            from oqlos.core.oql_parser import parse_oql
            if is_flat_oql(source):
                oql_doc = parse_oql(source, filename)
                return oql_doc_to_cql(oql_doc)
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
            self._goal_skipped = False # Reset for each goal
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

        if self._sensor_eval._auto_mock:
            self._sensor_eval.seed_sensors_from_conditions(doc)

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
            elif act_result == StepStatus.SKIPPED:
                status = StepStatus.SKIPPED

        elapsed = (time.monotonic() - t0) * 1000
        icon = {"passed": "✅", "failed": "❌", "error": "💥", "skipped": "⏭️"}.get(status.value, "⏭️")
        self.out.step(f"    {icon}", f"[{status.value}] {step.name}")

        return StepResult(
            name=f"{step.number}. {step.name}",
            status=status, message=message,
            duration_ms=elapsed, details=details,
        )

    # ── Action dispatch table ───────────────────────────────────────

    # ── Action Handlers (delegated to _interpreter_actions module) ──

    def _execute_action(self, act: CqlAction) -> StepStatus:
        """Dispatch action to specific handler based on kind."""
        if self._goal_skipped:
            return StepStatus.SKIPPED

        from oqlos.core._interpreter_actions import ACTION_HANDLERS

        handler = ACTION_HANDLERS.get(act.kind)
        if handler is not None:
            return handler(self, act)

        # Try flat action dispatch (SET, VAL, SAVE, etc. if kind is generic)
        if act.kind in ("set", "val", "save", "min", "max", "wait"):
            return self._exec_flat_action(act)

        self.out.warn(f"Unknown action kind: {act.kind}")
        return StepStatus.ERROR

    def _exec_flat_action(self, act: CqlAction) -> StepStatus:
        """Handle actions without arrows (SET 'PUMP' 'off', etc)."""
        from oqlos.core._interpreter_actions import (
            exec_action_set, exec_action_val, exec_action_save,
            exec_action_min_max, exec_action_wait
        )

        kind = act.kind.lower()
        if kind == "set":
            return exec_action_set(self, act)
        elif kind == "val":
            return exec_action_val(self, act)
        elif kind == "save":
            return exec_action_save(self, act)
        elif kind in ("min", "max"):
            return exec_action_min_max(self, act)
        elif kind == "wait":
            return exec_action_wait(self, act)
        return StepStatus.ERROR

    def _do_sleep(self, secs: float, label: str) -> None:
        """Perform sleep operation."""
        from oqlos.core._interpreter_actions import _do_sleep
        _do_sleep(self, secs, label)

    def _normalize_peripheral_value(self, resolved: str | None, value: str) -> Any:
        """Delegate to FirmwareExecutor."""
        return self._fw_exec.normalize_peripheral_value(resolved, value)

    def _coerce_generic_peripheral_value(self, value: Any) -> Any:
        """Delegate to ValueNormalizer."""
        return self._normalizer.coerce_generic_peripheral_value(value)

    def _exec_set_peripheral(self, act: CqlAction, value: str) -> StepStatus | None:
        """Execute SET for a peripheral while preserving legacy monkeypatch points."""
        fw = self._get_firmware()
        resolved = self._resolve_peripheral_id(act.target or "")
        normalized_value = self._normalize_peripheral_value(resolved, value)
        try:
            fw.set_peripheral(act.target or "", normalized_value)
        except Exception as exc:
            self.out.error(str(exc))
            return StepStatus.ERROR
        return None

    def _get_firmware(self):
        """Delegate to FirmwareExecutor."""
        return self._fw_exec._get_firmware()

    def _execute_firmware_action(self, act: CqlAction, args: str | None = None) -> StepStatus:
        """Delegate to FirmwareExecutor."""
        return self._fw_exec.execute_firmware_action(act, args)

    def _execute_plugin_action(self, act: CqlAction, args: str | None = None) -> StepStatus:
        """Delegate to FirmwareExecutor."""
        return self._fw_exec._execute_plugin_action(act, args)

    def _execute_legacy_firmware_action(self, act: CqlAction, args: str | None = None) -> StepStatus:
        """Delegate to FirmwareExecutor."""
        return self._fw_exec._execute_legacy_firmware_action(act, args)

    def _refresh_sensors_from_firmware(self) -> None:
        """Delegate to FirmwareExecutor."""
        self._fw_exec.refresh_sensors_from_firmware(self.sensor_values)

    def _auto_mock_sensor(self, sensor: str, cond, val: float) -> float:
        """Delegate to SensorEvaluator."""
        return self._sensor_eval.auto_mock_sensor(sensor, cond, val)

    def _compare_sensor(self, sensor: str, cond, val: float) -> tuple[bool, str]:
        """Delegate to SensorEvaluator."""
        return self._sensor_eval.compare_sensor(sensor, cond, val)

    _INLINE_IF_SPLIT_RE = re.compile(r"\s+(AND|OR)\s+", re.IGNORECASE)
    _INLINE_IF_CLAUSE_RE = re.compile(
        r"^\s*(?:['\"](?P<sensor_quoted>.+?)['\"]|\[(?P<sensor_bracket>[^\]]+)\])\s*"
        r"(?:\[(?P<op_bracket>[<>=!≤≥]+)\]|(?P<op>[<>=!≤≥]+))\s*"
        r"(?:['\"](?P<value_quoted>.+?)['\"]|\[(?P<value_bracket>[^\]]+)\])\s*$",
        re.IGNORECASE,
    )

    def _resolve_sensor_value(self, sensor: str) -> float:
        """Resolve a sensor or computed variable value from cache or variables."""
        base_sensor = sensor[1:] if sensor.startswith("Δ") else sensor
        if sensor in self.sensor_values:
            return float(self.sensor_values[sensor])

        if sensor.startswith("Δ"):
            return self._resolve_delta_sensor_value(base_sensor)

        if base_sensor in self.sensor_values:
            return float(self.sensor_values[base_sensor])

        numeric = self._coerce_float(self.vars.get(sensor))
        if numeric is not None:
            return float(numeric)
        numeric = self._coerce_float(self.vars.get(base_sensor))
        if numeric is not None:
            return float(numeric)
        return 0.0

    def _resolve_delta_sensor_value(self, base_sensor: str) -> float:
        """Best-effort delta fallback for Δ-sensors when no explicit value is stored."""
        now = time.monotonic()

        if base_sensor in self.sensor_values:
            current = float(self.sensor_values[base_sensor])
        else:
            numeric = self._coerce_float(self.vars.get(base_sensor))
            current = float(numeric) if numeric is not None else 0.0

        prev_value = self._coerce_float(self.vars.get(f"__delta_prev_value:{base_sensor}"))
        prev_time = self._coerce_float(self.vars.get(f"__delta_prev_time:{base_sensor}"))

        self.vars.set(f"__delta_prev_value:{base_sensor}", current)
        self.vars.set(f"__delta_prev_time:{base_sensor}", now)

        if prev_value is None or prev_time is None or now <= prev_time:
            return 0.0

        return float((current - float(prev_value)) / (now - float(prev_time)))

    def _resolve_windowed_delta_sensor_value(self, base_sensor: str, window_s: float) -> float:
        """Compute delta rate for Δ-sensor over a configured time window."""
        now = time.monotonic()
        if base_sensor in self.sensor_values:
            current = float(self.sensor_values[base_sensor])
        else:
            numeric = self._coerce_float(self.vars.get(base_sensor))
            current = float(numeric) if numeric is not None else 0.0

        state_key = f"__delta_window_state:{base_sensor}:{window_s}"
        prev_state = self.vars.get(state_key)
        prev_value = None
        prev_time = None
        if isinstance(prev_state, (tuple, list)) and len(prev_state) == 2:
            prev_value = self._coerce_float(prev_state[0])
            prev_time = self._coerce_float(prev_state[1])

        if prev_value is None or prev_time is None or now <= prev_time:
            self.vars.set(state_key, (current, now))
            return 0.0

        elapsed = now - float(prev_time)
        if elapsed <= 0:
            return 0.0

        effective_window = max(float(window_s), 0.001)
        denominator = effective_window if elapsed < effective_window else elapsed
        rate = float((current - float(prev_value)) / denominator)

        if elapsed >= effective_window:
            self.vars.set(state_key, (current, now))

        return rate

    @staticmethod
    def _extract_window_seconds(args: str | None) -> float | None:
        """Parse window metadata from action args, e.g. ``window_s=5.0``."""
        text = str(args or "").strip()
        if not text:
            return None
        match = re.search(r"window_s\s*=\s*([-+]?\d*\.?\d+)", text)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    def _resolve_condition_rhs(self, raw_value: str | None, fallback: float | None, fallback_unit: str) -> tuple[float | None, str]:
        """Resolve a condition RHS from raw DSL text or a parsed fallback."""
        text = str(raw_value or "").strip()
        if text:
            interpolated = self.vars.interpolate(text)
            if interpolated == text:
                stored = self.vars.get(text)
                if stored is not None:
                    interpolated = str(stored)
            numeric = self._coerce_float(interpolated)
            if numeric is not None:
                unit = ""
                match = re.match(r"\s*[-+]?\d*\.?\d+(.*)$", interpolated.replace(",", "."))
                if match:
                    unit = match.group(1).strip()
                return float(numeric), unit or fallback_unit
        return fallback, fallback_unit

    def _evaluate_resolved_condition(
        self,
        *,
        sensor: str,
        operator: str,
        threshold: float | None,
        unit: str,
        on_fail: str,
        fail_message: str,
    ) -> StepStatus:
        """Evaluate a single scalar condition after RHS resolution."""
        if sensor == "Timer":
            self.out.step("    ⏱️ ", f"Timer {operator} {threshold}s → OK (simulated)")
            return StepStatus.PASSED

        if threshold is None:
            self.out.warn(f"Could not resolve condition value for {sensor} {operator}")
            return StepStatus.ERROR

        cond = CqlCondition(
            sensor=sensor,
            operator=operator,
            value=threshold,
            unit=unit,
            on_fail=on_fail,
            fail_message=fail_message,
        )
        val = self._resolve_sensor_value(sensor)

        if self._sensor_eval._auto_mock and self.mode == "dry-run":
            val = self._sensor_eval.auto_mock_sensor(sensor, cond, val)

        ok, desc = self._sensor_eval.compare_sensor(sensor, cond, val)
        if ok:
            self.out.step("    ✅", f"{desc} → PASS")
            return StepStatus.PASSED

        self.out.step("    ❌", f"{desc} → {on_fail}: {fail_message}")
        if on_fail == "ERROR":
            self.errors.append(f"{sensor}: {fail_message}")
            return StepStatus.FAILED
        return StepStatus.WARNING

    def _eval_condition_clause(
        self,
        token: str,
        expression: str,
    ) -> tuple[bool | None, str, StepStatus | None]:
        """Evaluate a single condition clause (sensor op value).

        Returns: (ok_result, description, error_status)
            - ok_result: bool if successful, None if error
            - description: string description of the condition
            - error_status: StepStatus.ERROR if parsing failed, None if ok
        """
        match = self._INLINE_IF_CLAUSE_RE.match(token)
        if not match:
            self.out.warn(f"Unsupported IF expression: {expression}")
            return None, "", StepStatus.ERROR

        sensor = (match.group("sensor_quoted") or match.group("sensor_bracket") or "").strip()
        operator = (match.group("op") or match.group("op_bracket") or "").strip()
        raw_value = (match.group("value_quoted") or match.group("value_bracket") or "").strip()

        threshold, unit = self._resolve_condition_rhs(raw_value, None, "")
        if threshold is None:
            self.out.warn(f"Could not resolve IF expression value: {raw_value}")
            return None, "", StepStatus.ERROR

        cond = CqlCondition(sensor=sensor, operator=operator, value=threshold, unit=unit)
        val = self._resolve_sensor_value(sensor)

        if self._sensor_eval._auto_mock and self.mode == "dry-run":
            val = self._sensor_eval.auto_mock_sensor(sensor, cond, val)

        ok, desc = self._sensor_eval.compare_sensor(sensor, cond, val)
        return ok, desc, None

    def _evaluate_inline_condition_expression(
        self,
        expression: str,
        *,
        on_fail: str = "",
        fail_message: str = "",
    ) -> StepStatus:
        """Evaluate flat IF expressions, including OR/AND chains. CC≈8"""
        tokens = self._tokenize_condition_expression(expression)
        if not tokens:
            return StepStatus.ERROR

        result, descriptions = self._aggregate_condition_results(tokens, expression)
        if result is None:
            return StepStatus.ERROR

        return self._finalize_condition_result(
            result, descriptions, on_fail, fail_message or expression
        )

    def _tokenize_condition_expression(self, expression: str) -> list[str]:
        """Split expression into tokens (clauses and AND/OR connectors)."""
        return [token for token in self._INLINE_IF_SPLIT_RE.split(str(expression or "").strip()) if token]

    def _aggregate_condition_results(
        self, tokens: list[str], expression: str
    ) -> tuple[bool | None, list[str]]:
        """Evaluate all condition clauses and aggregate with AND/OR logic."""
        result: bool | None = None
        pending_connector = "AND"
        descriptions: list[str] = []

        for token in tokens:
            connector = token.upper()
            if connector in {"AND", "OR"}:
                pending_connector = connector
                descriptions.append(connector)
                continue

            ok, desc, error = self._eval_condition_clause(token, expression)
            if error:
                return None, descriptions

            descriptions.append(desc)
            result = self._apply_connector(result, ok, pending_connector)

        return result, descriptions

    def _apply_connector(self, current: bool | None, clause_result: bool, connector: str) -> bool:
        """Apply AND/OR logic to combine condition results."""
        if current is None:
            return clause_result
        if connector == "AND":
            return current and clause_result
        return current or clause_result

    def _finalize_condition_result(
        self, result: bool, descriptions: list[str], on_fail: str, fail_message: str
    ) -> StepStatus:
        """Emit output and return appropriate status based on final result."""
        desc_str = " ".join(descriptions)
        if result:
            self.out.step("    ✅", f"{desc_str} → PASS")
            return StepStatus.PASSED

        self.out.step("    ❌", f"{desc_str} → {on_fail}: {fail_message}")
        if on_fail == "ERROR":
            self.errors.append(fail_message)
            return StepStatus.FAILED
        return StepStatus.WARNING

    def _evaluate_condition(self, act: CqlAction) -> StepStatus:
        """Evaluate a condition using the sensor evaluator."""
        cond = act.condition
        if not cond and act.args:
            return self._evaluate_inline_condition_expression(act.args)
        if not cond:
            return StepStatus.PASSED

        sensor = cond.sensor
        if cond.operator == "∈" and cond.value_min is not None and cond.value_max is not None:
            if sensor == "Timer":
                self.out.step("    ⏱️ ", f"Timer {cond.operator} {cond.value}s → OK (simulated)")
                return StepStatus.PASSED

            val = self._resolve_sensor_value(sensor)
            if self._sensor_eval._auto_mock and self.mode == "dry-run":
                val = self._sensor_eval.auto_mock_sensor(sensor, cond, val)

            ok, desc = self._sensor_eval.compare_sensor(sensor, cond, val)
            if ok:
                pass_msg = f" → {cond.pass_message}" if cond.pass_message else " → PASS"
                self.out.step("    ✅", f"{desc}{pass_msg}")
                return StepStatus.PASSED

            self.out.step("    ❌", f"{desc} → {cond.on_fail}: {cond.fail_message}")
            if cond.on_fail == "ERROR":
                self.errors.append(f"{sensor}: {cond.fail_message}")
                return StepStatus.FAILED
            return StepStatus.WARNING

        window_s = None
        if sensor.startswith("Δ"):
            window_s = self._extract_window_seconds(act.args)
            if window_s is not None and window_s > 0:
                base_sensor = sensor[1:]
                delta_rate = self._resolve_windowed_delta_sensor_value(base_sensor, window_s)
                self.sensor_values[sensor] = delta_rate

        rhs_text = None if window_s is not None else act.args
        threshold, unit = self._resolve_condition_rhs(rhs_text, cond.value, cond.unit)
        return self._evaluate_resolved_condition(
            sensor=sensor,
            operator=cond.operator,
            threshold=threshold,
            unit=unit,
            on_fail=cond.on_fail,
            fail_message=cond.fail_message,
        )
