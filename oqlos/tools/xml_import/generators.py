#!/usr/bin/env python3
"""DSL, CQL, and JSON generators from parsed DeviceReport."""

from __future__ import annotations

import re
from typing import Any

from .models import DeviceReport, Operation
from ._utils import (
    is_compressor_output,
    is_pump_output,
    normalize_flow_value,
    normalize_output_name,
    normalize_set_value,
)


def _mode_symbol(mode: str) -> str:
    """Get symbol for mode."""
    return {
        "inRangeOK": "∈",
        "minOk": "≥",
        "maxOk": "≤",
        "maxErr": "≤",
        "minErr": "≥",
    }.get(mode, "?")


def _format_range(p) -> str:
    """Format range constraint for DSL."""
    if p.mode == "inRangeOK" and p.min_val is not None and p.max_val is not None:
        return f"∈ [{p.min_val}, {p.max_val}]"
    if p.mode in ("minOk", "minErr") and p.min_val is not None:
        return f"≥ {p.min_val}"
    if p.mode in ("maxOk", "maxErr") and p.max_val is not None:
        return f"≤ {p.max_val}"
    if p.max_val is not None:
        return f"≤ {p.max_val}"
    return ""


def _mode_action(mode: str) -> str:
    """Get action for mode."""
    if mode.endswith("Err"):
        return "ERROR"
    if mode.endswith("Ok"):
        return "PASS"
    return "PASS"


# ── Shared CQL helpers (used by generate_cql and _generate_cql_for_goal) ──


def _quote_oql(value: Any) -> str:
    """Quote an OQL token with the canonical single-quoted SET syntax."""
    text = str(value or "").strip()
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _emit_set(a: callable, target: str, value: Any, *, indent: str = "  ") -> None:
    a(f"{indent}SET {_quote_oql(target)} {_quote_oql(value)}")


def _emit_cql_output(out, a: callable) -> None:
    """Emit CQL SET line for a single output."""
    if is_pump_output(out.name):
        if out.value.lower() == "off":
            _emit_set(a, "pompa", "0")
        elif out.value.lower() == "on":
            _emit_set(a, "pompa", "1")
        else:
            raw_value = re.sub(r"\s+", " ", out.value.strip())
            raw_value = re.sub(r"^(\d+(?:[\.,]\d+)?)([A-Za-z%]+)$", r"\1 \2", raw_value)
            _emit_set(a, "pompa", raw_value)
    elif is_compressor_output(out.name):
        _emit_set(a, "sprężarka", normalize_set_value(out.value, default_unit="l/min"))
    else:
        _emit_set(a, normalize_output_name(out.name), normalize_set_value(out.value))


def _emit_cql_param(p, a: callable, *, indent: str = "  ") -> None:
    """Emit CQL lines for a single parameter."""
    if p.mode == "Off":
        return
    if p.sensor == "operator":
        _emit_set(a, p.description, "1", indent=indent)
        if p.save:
            a(f"{indent}SAVE [{p.description}]")
        return
    if p.sensor == "timer":
        if p.max_val is not None:
            a(f"{indent}SET WAIT '{p.max_val} s'")
        elif p.min_val is not None:
            a(f"{indent}SET WAIT '{p.min_val} s'")
        return
    _emit_cql_sensor_param(p, a, indent=indent)


def _emit_cql_sensor_param(p, a: callable, *, indent: str = "  ") -> None:
    """Emit CQL lines for a sensor (AI01, AI02, etc.) parameter."""
    unit = p.unit or "mbar"
    if p.mode == "inRangeOK" and p.min_val is not None and p.max_val is not None:
        a(f"{indent}MIN [{p.sensor}] = [{p.min_val} {unit}]")
        a(f"{indent}MAX [{p.sensor}] = [{p.max_val} {unit}]")
        a(f"{indent}VAL [{p.sensor}] [{unit}]")
        a(f'{indent}IF [{p.sensor}] [<] [{p.min_val} {unit}] ELSE ERROR "{p.description or p.sensor + " poza zakresem"}"')
    elif p.mode in ("minOk", "minErr") and p.min_val is not None:
        a(f"{indent}MIN [{p.sensor}] = [{p.min_val} {unit}]")
        a(f"{indent}VAL [{p.sensor}] [{unit}]")
        a(f'{indent}IF [{p.sensor}] [<] [{p.min_val} {unit}] ELSE ERROR "{p.description or p.sensor}"')
    elif p.mode in ("maxOk", "maxErr") and p.max_val is not None:
        a(f"{indent}MAX [{p.sensor}] = [{p.max_val} {unit}]")
        a(f"{indent}VAL [{p.sensor}] [{unit}]")
        a(f'{indent}IF [{p.sensor}] [>] [{p.max_val} {unit}] ELSE ERROR "{p.description or p.sensor}"')
    if p.save:
        a(f"{indent}SAVE [{p.sensor}]")


# ── DSL output/param helpers ──


def _emit_dsl_output(out, a: callable) -> None:
    """Emit DSL output line for a single output."""
    if out.value.lower() == "off":
        a(f"       → {out.name.capitalize() if out.name == 'pump' else out.name}.off")
    elif out.value.lower() == "on":
        a(f"       → {out.name}.on")
    else:
        a(f"       → {out.name.capitalize() if out.name == 'pump' else out.name}.set {out.value}")


def _emit_dsl_param(p, a: callable) -> None:
    """Emit DSL param line for a single parameter."""
    if p.mode == "Off":
        return
    if p.sensor == "operator":
        a(f'       → Operator.confirm "{p.description}"')
        if p.save:
            a("       SAVE: operator.result")
        return
    if p.sensor == "timer":
        rng = _format_range(p)
        unit = "s"
        action = _mode_action(p.mode)
        if p.description:
            a(f'       # {p.description}')
        if p.mode == "maxOk":
            a(f"       Timer {rng} {unit}                     | WAIT")
        else:
            a(f'       Timer {rng} {unit}                     | {action} "{p.description}"')
        return
    # AI01, AI02, AI03
    rng = _format_range(p)
    unit = p.unit or "mbar"
    action = _mode_action(p.mode)
    desc = p.description or p.sensor
    pad = " " * max(1, 30 - len(f"{p.sensor} {rng} {unit}"))
    a(f"       {p.sensor} {rng} {unit}{pad}| {action} \"{desc}\"")
    if p.save:
        a(f"       SAVE: {p.sensor}.value")


# ── JSON step/validation helpers ──


def _build_steps_from_op(op: Operation) -> list[dict[str, Any]]:
    """Build step dicts from a single operation's outputs and params."""
    steps: list[dict[str, Any]] = []
    for out in op.outputs:
        if out.name == "pump":
            if out.value.lower() == "off":
                steps.append({"id": f"{op.op_id}-out-{out.name}",
                              "action": "SET_PUMP", "peripheral": "pump-main", "value": 0})
            else:
                pv = re.sub(r'[^\d]', '', out.value) or "5"
                steps.append({"id": f"{op.op_id}-out-{out.name}",
                              "action": "SET_PUMP", "peripheral": "pump-main", "value": int(pv)})
        else:
            steps.append({"id": f"{op.op_id}-out-{out.name}",
                          "action": "SET_VALVE", "peripheral": out.name,
                          "value": out.value.lower() == "on"})
    for p in op.params:
        if p.mode == "Off":
            continue
        if p.sensor == "operator":
            steps.append({"id": f"{op.op_id}-prm-operator",
                          "action": "OPERATOR_CONFIRM", "message": p.description})
        elif p.sensor == "timer":
            dur_ms = int((p.max_val or 10) * 1000)
            steps.append({"id": f"{op.op_id}-prm-timer",
                          "action": "WAIT", "duration": dur_ms})
        else:
            step: dict[str, Any] = {
                "id": f"{op.op_id}-prm-{p.sensor}",
                "action": "READ_SENSOR",
                "peripheral": p.sensor.lower().replace("ai", "ai-sensor-"),
            }
            steps.append(step)
            _append_sensor_assertion(steps, op, p)
    return steps


def _append_sensor_assertion(steps: list, op: Operation, p) -> None:
    """Append a sensor assertion step if the param has range constraints."""
    if p.mode == "Off":
        return
    assertion: dict[str, Any] = {
        "id": f"{op.op_id}-assert-{p.sensor}",
        "action": "ASSERT_RANGE",
        "peripheral": p.sensor.lower().replace("ai", "ai-sensor-"),
        "mode": p.mode,
    }
    if p.min_val is not None:
        assertion["min"] = p.min_val
    if p.max_val is not None:
        assertion["max"] = p.max_val
    assertion["unit"] = p.unit or "mbar"
    assertion["errorMessage"] = p.description or f"{p.sensor} poza zakresem"
    steps.append(assertion)


def _build_validation_criteria(ops: list[Operation]) -> list[dict[str, Any]]:
    """Build validation criteria from operations' sensor params."""
    criteria: list[dict[str, Any]] = []
    for op in ops:
        for p in op.params:
            if p.mode == "Off" or p.sensor in ("timer", "operator"):
                continue
            crit: dict[str, Any] = {
                "peripheral": p.sensor.lower().replace("ai", "ai-sensor-"),
                "unit": p.unit or "mbar",
            }
            if p.mode == "inRangeOK" and p.min_val is not None and p.max_val is not None:
                crit["condition"] = f"value >= {p.min_val} and value <= {p.max_val}"
            elif p.mode in ("minOk", "minErr") and p.min_val is not None:
                crit["condition"] = f"value >= {p.min_val}"
            elif p.mode in ("maxOk", "maxErr") and p.max_val is not None:
                crit["condition"] = f"value <= {p.max_val}"
            crit["errorMessage"] = p.description or f"{p.sensor} poza zakresem"
            criteria.append(crit)
    return criteria


def generate_dsl(report: DeviceReport) -> str:
    """Generate human-readable DSL text from parsed report."""
    lines: list[str] = []
    a = lines.append

    a(f"# {'=' * 77}")
    a(f"# DSL: {report.df_name} — {report.dt_name}")
    a(f"# Wygenerowano z: {report.report_id}")
    a(f"# Data: {report.date}")
    if report.cs_name:
        a(f"# Klient: {report.cs_name}, {report.cs_city}")
    a(f"# {'=' * 77}")
    a("")

    a(f'DEVICE_TYPE: "{report.df_name}"')
    a(f'DEVICE_MODEL: "{report.dt_name}"')
    if report.dt_manufacturer:
        a(f'MANUFACTURER: "{report.dt_manufacturer}"')
    a("")

    if report.intervals:
        a("INTERVALS:")
        for tt_id, info in sorted(report.intervals.items()):
            a(f'  - {tt_id}: "{info["name"]}"   period: {info["period"]} months')
        a("")

    for tr in report.test_runs:
        _emit_dsl_test_run(report, tr, a)

    _emit_dsl_sensors(report, a)
    _emit_dsl_metadata(report, a)

    return f"{chr(10).join(lines)}\n"


def _emit_dsl_test_run(report: DeviceReport, tr, a: callable) -> None:
    """Emit DSL lines for a single test run."""
    a(f"# {'-' * 77}")
    a(f"# SCENARIUSZ: {tr.name}")
    a(f"# {'-' * 77}")
    a("")

    safe_name = re.sub(r'\W+', '', report.dt_name.replace(" ", ""))
    tr_label = re.sub(r'\W+', '', tr.name.replace(" ", ""))
    a(f"@{safe_name}.{tr_label}")
    a(f'  description: "{tr.name}"')
    if tr.do_intervals:
        a(f"  intervals: [{', '.join(tr.do_intervals)}]")
    a("")

    current_goal_num = None
    for op in tr.operations:
        parts = op.lp.split(".")
        goal_num = parts[0] if parts else "0"

        if goal_num != current_goal_num:
            current_goal_num = goal_num
            a(f"  # === GOAL {goal_num}: {op.name.upper()} ===")
            goal_label = re.sub(r'\W+', '', op.name.replace(" ", ""))
            a(f"  {goal_label}:")
            if op.alarm_l2:
                a(f'    alarm: "{op.alarm_l2.strip()}"')
            if any(p.editable for p in op.params):
                a("    editable: true")
            a("")

        a(f"    {op.lp}. {op.name}:")
        for out in op.outputs:
            _emit_dsl_output(out, a)
        for p in op.params:
            _emit_dsl_param(p, a)
        a("")


def _emit_dsl_sensors(report: DeviceReport, a: callable) -> None:
    """Emit SENSORS section."""
    sensors_used = set()
    for tr in report.test_runs:
        for op in tr.operations:
            for p in op.params:
                if p.sensor.startswith("AI"):
                    sensors_used.add((p.sensor, p.unit))
    if sensors_used:
        a("SENSORS:")
        for s, u in sorted(sensors_used):
            a(f'  {s}: "Czujnik ciśnienia"   unit: {u or "mbar"}')
        a("")


def _emit_dsl_metadata(report: DeviceReport, a: callable) -> None:
    """Emit META section."""
    a(f"# {'=' * 77}")
    a("META:")
    a(f'  source: "{report.report_id}"')
    a(f'  device_id: "{report.dv_id}"')
    a(f'  device_number: "{report.dv_number}"')
    a(f'  barcode: "{report.dv_barcode}"')
    a(f'  customer: "{report.cs_name}"')
    a(f'  location: "{report.cs_city}, {report.cs_street}"')
    a(f'  test_date: "{report.date}"')
    a(f'  result: "{report.result}"')


def generate_cql(report: DeviceReport) -> str:
    """Generate CQL (Connex Query Language) text from parsed report."""
    lines: list[str] = []
    a = lines.append

    a("# CQL — Connex Query Language")
    a(f"# Wygenerowano z: {report.report_id}")
    if report.date:
        a(f"# Data: {report.date}")
    a("")

    title = report.df_name
    for tr in report.test_runs:
        if tr.name:
            title = f"{report.dt_name}: {tr.name}"
            break
    a(f"SCENARIO: {title}")
    a("")

    for tr in report.test_runs:
        goal_groups: dict[str, list[Operation]] = {}
        for op in tr.operations:
            parts = op.lp.split(".")
            goal_num = parts[0] if parts else "0"
            goal_groups.setdefault(goal_num, []).append(op)

        for goal_num, ops in sorted(goal_groups.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
            a(f"GOAL: {ops[0].name}")
            for op in ops:
                for out in op.outputs:
                    _emit_cql_output(out, a)
                for p in op.params:
                    _emit_cql_param(p, a)
            a("")

    return f"{chr(10).join(lines)}\n"


def _generate_cql_for_goal(ops: list[Operation]) -> str:
    """Generate CQL code block for a single goal (used in library.goals[].code)."""
    lines: list[str] = []
    a = lines.append

    for op in ops:
        for out in op.outputs:
            _emit_cql_output(out, a)
        for p in op.params:
            _emit_cql_param(p, a)

    return "\n".join(lines)


def generate_goals_json(report: DeviceReport) -> dict:
    """Generate JSON goals structure for REST API."""
    all_goals = []

    for tr in report.test_runs:
        goal_groups: dict[str, list[Operation]] = {}
        for op in tr.operations:
            parts = op.lp.split(".")
            goal_num = parts[0] if parts else "0"
            goal_groups.setdefault(goal_num, []).append(op)

        for goal_num, ops in sorted(goal_groups.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
            first_op = ops[0]
            goal_id = f"goal-{goal_num}-{re.sub(r'[^a-z0-9]+', '-', first_op.name.lower()).strip('-')}"

            steps = []
            for op in ops:
                steps.extend(_build_steps_from_op(op))

            validation_criteria = _build_validation_criteria(ops)
            cql_code = _generate_cql_for_goal(ops)

            goal: dict[str, Any] = {
                "id": goal_id,
                "name": first_op.name,
                "code": cql_code,
                "description": f"{first_op.display_l1} {first_op.display_l2}" if first_op.display_l2 else first_op.display_l1,
                "steps": steps,
                "expectedResult": f"Wynik: {first_op.result}" if first_op.result else "",
                "validationCriteria": validation_criteria,
            }
            if first_op.alarm_l2:
                goal["alarm"] = first_op.alarm_l2.strip()
            if any(p.editable for op in ops for p in op.params):
                goal["editable"] = True

            all_goals.append(goal)

    config = {
        "systemVars": {},
        "device": {
            "type": report.dt_name,
            "manufacturer": report.dt_manufacturer,
            "family": report.df_name,
        },
        "intervals": report.intervals,
        "source": report.report_id,
    }

    return {
        "goals": all_goals,
        "config": config,
    }
