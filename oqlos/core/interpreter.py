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

import yaml

import oqlos.config as oql_config
from oqlos.core.base import (
    BaseInterpreter,
    ScriptResult,
    StepResult,
    StepStatus,
)
from oqlos.core._dsl_helpers import _parse_numeric_value
from oqlos.models.dsl_models import CqlAction, CqlDocument, CqlGoal, CqlStep
from oqlos.core.cql_parser import parse_cql, validate_cql
from oqlos.hardware.firmware_adapter import _PERIPHERAL_MAP
from oqlos.hardware.plugin_gateway import PluginHardwareGateway


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
        bridge_url: str | None = None,
        yaml_output: bool = False,
        use_plugin_gateway: bool = True,
    ):
        super().__init__(variables=variables, quiet=quiet, bridge_url=bridge_url)
        self.mode = mode  # validate, dry-run, execute
        self._firmware = None
        self._firmware_url = firmware_url
        self._skip_waits = skip_waits
        self._auto_mock = auto_mock and mode == "dry-run"
        self._goal_skipped = False # Track if current goal execution should be skipped (flat IF)
        self._yaml_output = yaml_output
        self._use_plugin_gateway = use_plugin_gateway
        # Use plugin gateway instead of old hardware system
        if use_plugin_gateway:
            self._plugin_gateway = PluginHardwareGateway(mode=mode)
        else:
            self._plugin_gateway = None
        # Seed with defaults, then overlay user-provided values
        self.sensor_values: dict[str, float] = dict(self.DEFAULT_MOCK_SENSORS)
        if sensor_values:
            self.sensor_values.update(sensor_values)

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        """Best-effort float coercion for config values."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        parsed = _parse_numeric_value(str(value))
        if parsed is not None:
            return float(parsed)
        try:
            return float(str(value).replace(",", ".").strip())
        except Exception:
            return None

    def _resolve_peripheral_id(self, target: str) -> str | None:
        """Resolve a known target name to a firmware peripheral id."""
        normalized = target.strip().lower().replace(" ", "-").replace("_", "-")
        return _PERIPHERAL_MAP.get(normalized)

    def _get_pump_flow_full_scale_lpm(self) -> float:
        """Resolve the flow rate that maps to 100% PWM."""
        for key in ("PUMP_FLOW_FULL_SCALE_LPM", "pump_flow_full_scale_lpm"):
            raw = self.vars.get(key)
            scale = self._coerce_float(raw)
            if scale and scale > 0:
                return scale

        try:
            settings = oql_config.get_settings()
            scale = self._coerce_float(getattr(settings, "pump_flow_full_scale_lpm", None))
            if scale and scale > 0:
                return scale
        except Exception:
            pass

        return 10.0

    def _normalize_pump_power(self, raw_value: str) -> float:
        """Convert a pump command value to a PWM percentage."""
        text = self.vars.interpolate((raw_value or "").strip())
        lowered = text.lower().strip()

        if lowered in {"on", "true"}:
            return 100.0
        if lowered in {"off", "false"}:
            return 0.0

        numeric = self._coerce_float(text)
        if numeric is None:
            return 0.0

        compact = lowered.replace(" ", "")
        if "l/min" in compact or compact.endswith("lpm"):
            scale = self._get_pump_flow_full_scale_lpm()
            if scale <= 0:
                return 0.0
            numeric = numeric / scale * 100.0

        return max(0.0, min(100.0, float(numeric)))

    def _normalize_valve_value(self, raw_value: Any) -> bool:
        """Convert a valve command value to a boolean state."""
        if isinstance(raw_value, bool):
            return raw_value
        if isinstance(raw_value, (int, float)):
            return float(raw_value) != 0.0

        text = self.vars.interpolate(str(raw_value or "")).strip().lower()
        if text in {"on", "true", "open", "1", "yes"}:
            return True
        if text in {"off", "false", "closed", "close", "0", "no"}:
            return False

        numeric = self._coerce_float(text)
        if numeric is not None:
            return numeric != 0.0
        return bool(text)

    def _normalize_lung_value(self, raw_value: Any) -> int:
        """Convert a lung command value to a cycle count."""
        text = self.vars.interpolate(str(raw_value or "")).strip().lower()
        if text in {"off", "false", "stop", "0"}:
            return 0

        numeric = self._coerce_float(text)
        if numeric is None:
            return 5
        return max(0, int(numeric))

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

    def _exec_set_peripheral(self, act: CqlAction, value: str) -> StepStatus | None:
        fw = self._get_firmware()
        normalized_value = value
        resolved = self._resolve_peripheral_id(act.target or "")
        if resolved and resolved.startswith("pump"):
            normalized_value = self._normalize_pump_power(value)
        elif resolved and resolved.startswith("valve"):
            normalized_value = self._normalize_valve_value(value)
        elif resolved and resolved.startswith("lung"):
            normalized_value = self._normalize_lung_value(value)
        elif isinstance(value, str):
            lowered = value.lower()
            if lowered in {"on", "true"}:
                normalized_value = 1
            elif lowered in {"off", "false"}:
                normalized_value = 0
            else:
                numeric = self._coerce_float(value)
                if numeric is not None:
                    normalized_value = int(numeric) if numeric.is_integer() else numeric
        try:
            fw.set_peripheral(act.target or "", normalized_value)
        except Exception as exc:
            self.errors.append(str(exc))
            self.out.error(str(exc))
            return StepStatus.ERROR

        return None

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

    def _execute_firmware_action(self, act: CqlAction, args: str | None = None) -> StepStatus:
        """Execute action using plugin gateway when available, otherwise legacy firmware."""
        if self._use_plugin_gateway and self._plugin_gateway:
            return self._execute_plugin_action(act, args)
        else:
            return self._execute_legacy_firmware_action(act, args)

    def _execute_plugin_action(self, act: CqlAction, args: str | None = None) -> StepStatus:
        """Execute action using the new plugin gateway system."""
        target = act.target
        method = act.method
        to_send = args if args is not None else self.vars.interpolate(act.args)

        try:
            # Map DSL targets to plugin commands
            if method in {"set", "off"}:
                # Pump command
                power_pct = self._normalize_pump_power(to_send) if method == "set" else 0.0
                success = self._plugin_gateway.set_pump(power_pct)
                if success:
                    self.vars.set(target, to_send)
                    self.out.step("    →", f"{act.target}.{act.method} {to_send}")
                    return StepStatus.PASSED
                else:
                    self.out.error(f"{act.target}.{act.method} FAILED: plugin error")
                    return StepStatus.FAILED

            elif method in {"open", "close"}:
                # Valve command
                value = (method == "open")
                success = self._plugin_gateway.set_valve(target, value)
                if success:
                    self.vars.set(target, value)
                    self.out.step("    →", f"{act.target}.{act.method} {value}")
                    return StepStatus.PASSED
                else:
                    self.out.error(f"{act.target}.{act.method} FAILED: plugin error")
                    return StepStatus.FAILED

            elif method == "reciprocate":
                # Lung command
                success = self._plugin_gateway.set_lung()
                if success:
                    self.out.step("    →", f"{act.target}.{act.method}")
                    return StepStatus.PASSED
                else:
                    self.out.error(f"{act.target}.{act.method} FAILED: plugin error")
                    return StepStatus.FAILED

            else:
                self.out.warn(f"Unknown method {method} for target {target}")
                return StepStatus.PASSED

        except Exception as exc:
            self.out.error(f"Plugin execution error: {exc}")
            return StepStatus.FAILED

    def _execute_legacy_firmware_action(self, act: CqlAction, args: str | None = None) -> StepStatus:
        """Execute action on real/simulated firmware (legacy fallback)."""
        to_send = args if args is not None else self.vars.interpolate(act.args)
        res = self.firmware.dispatch_action(act.target, act.method, to_send)
        if res.get("ok"):
            self.out.step("    →", f"{act.target}.{act.method} {to_send} ({res.get('detail')})")
            return StepStatus.PASSED
        else:
            self.out.error(f"{act.target}.{act.method} FAILED: {res.get('detail')}")
            return StepStatus.FAILED

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
