"""
Action handlers for CQL Interpreter.

Extracted from interpreter.py to reduce god module complexity.
Each handler is a focused function with CC<10.
"""

from __future__ import annotations

import re
import time
from typing import Any, TYPE_CHECKING

from oqlos.core._action_motor2 import (
    _post_motor2_move_relative,
    _post_motor2_reciprocate,
    _post_motor2_stop,
    _try_exec_motor2_set,
)
from oqlos.models.dsl_models import CqlAction, CqlCondition

if TYPE_CHECKING:
    from oqlos.core.interpreter import CqlInterpreter
    from oqlos.core.base import StepStatus


_ACTION_TOKEN_RE = re.compile(r'"([^"]*)"|\'([^\']*)\'|(\S+)')


def _extract_action_tokens(text: str) -> list[str]:
    """Split an action line into quoted and bare tokens."""
    tokens: list[str] = []
    for match in _ACTION_TOKEN_RE.finditer(text or ""):
        tokens.append(next(group for group in match.groups() if group is not None))
    return tokens


def _drop_command_token(act: CqlAction) -> list[str]:
    """Return action tokens without the leading command name."""
    tokens = _extract_action_tokens(act.args or act.raw)
    command = str(act.method or "").strip().upper()
    if command and tokens and tokens[0].upper() == command:
        return tokens[1:]
    return tokens


def _coerce_expected_value(value: Any) -> Any:
    """Convert string tokens into comparable scalar values when possible."""
    if isinstance(value, (bool, int, float)) or value is None:
        return value

    text = str(value).strip()
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False

    try:
        numeric = float(text.replace(",", "."))
    except ValueError:
        return text
    return int(numeric) if numeric.is_integer() else numeric


def _compare_values(actual: Any, operator: str, expected: Any) -> bool:
    """Compare actual vs expected using a lightweight assertion operator."""
    op = (operator or "==").strip().lower()
    left = _coerce_expected_value(actual)
    right = _coerce_expected_value(expected)

    if op in {"=", "=="}:
        return left == right
    if op == "!=":
        return left != right
    if op == "contains":
        return str(right) in str(left)

    try:
        left_num = float(left)
        right_num = float(right)
    except (TypeError, ValueError):
        return False

    if op == ">":
        return left_num > right_num
    if op == ">=":
        return left_num >= right_num
    if op == "<":
        return left_num < right_num
    if op == "<=":
        return left_num <= right_num
    return False


def _oql_quote(value: Any) -> str:
    text = str(value or "")
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _format_set_command(target: Any, value: Any) -> str:
    return f"SET {_oql_quote(target)} {_oql_quote(value)}"


def _get_nested_value(payload: Any, path: str) -> Any:
    """Resolve a dotted JSON-like path from a nested structure."""
    current = payload
    for part in str(path or "").split("."):
        if part == "":
            continue
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
            continue
        if isinstance(current, list) and part.isdigit():
            idx = int(part)
            if idx >= len(current):
                return None
            current = current[idx]
            continue
        return None
    return current


def _record_failure(interp: "CqlInterpreter", key: str, message: str) -> "StepStatus":
    """Record a failing diagnostic/assertion in interpreter state."""
    interp.vars.set(f"failure:{key}", True)
    interp.errors.append(message)
    interp.out.error(message)
    from oqlos.core.base import StepStatus
    return StepStatus.FAILED


def _mark_success(interp: "CqlInterpreter", key: str) -> None:
    """Mark a diagnostic target as passing."""
    interp.vars.set(f"failure:{key}", False)


def _normalize_bool(value: Any) -> bool | None:
    """Normalize a valve-style state token into a boolean."""
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "on", "open", "opened", "yes"}:
        return True
    if text in {"0", "false", "off", "closed", "close", "no"}:
        return False
    return None


def _lookup_peripheral_state(interp: "CqlInterpreter", target: str) -> Any:
    """Resolve a peripheral or valve state from stored variables."""
    direct = interp.vars.get(target)
    if direct is not None:
        return direct

    for key, value in interp.vars.all().items():
        try:
            if interp._resolve_peripheral_id(str(key)) == target:
                return value
        except Exception:
            continue
    return None


def _mock_api_response(interp: "CqlInterpreter", endpoint: str) -> dict[str, Any]:
    """Return deterministic API payloads for dry-run diagnostics."""
    normalized = str(endpoint or "").strip()
    if normalized == "/api/v1/hardware/health":
        return {
            "mode": "real",
            "modbus-adc": "ok",
            "motor": "ok",
            "modbus": "ttyACM0",
        }
    if normalized == "/api/v1/hardware/identify":
        return {
            "adapters": {
                "motor-dri0050": {"status": "ok"},
                "motor-tic249": {"status": "ok"},
                "modbus-io": {"status": "ok"},
                "modbus-adc": {"status": "ok"},
            }
        }
    if normalized == "/api/v1/peripherals":
        return {"peripherals": interp.vars.all()}
    if normalized == "/api/v1/state":
        return {
            "variables": interp.vars.all(),
            "sensors": dict(interp.sensor_values),
        }
    return {"ok": True, "path": normalized}


def exec_action_task(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute TASK action."""
    args_interpolated = interp.vars.interpolate(act.args)
    interp.out.step("    🔨", args_interpolated)
    from oqlos.core.base import StepStatus
    return StepStatus.PASSED


def exec_action_save(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute SAVE action."""
    val = interp.vars.get(act.target)
    if val is None:
        val = interp.sensor_values.get(act.target)
    if val is None:
        val = interp.sensor_values.get(act.target, 0.0) if act.target.startswith("AI") else "OK"
    interp.vars.set(act.target, val)
    interp.out.step("    💾", f"SAVE {act.target} = {val}")
    from oqlos.core.base import StepStatus
    return StepStatus.PASSED


def parse_wait_secs(raw: str) -> float:
    """Parse a WAIT value to seconds. Default unit is ms."""
    low = raw.lower().strip()
    match = re.search(r"[-+]?\d*\.?\d+", low.replace(",", "."))
    if not match:
        return 0.0
    num = float(match.group(0))
    if "s" in low and "ms" not in low:
        return num  # explicit seconds
    # bare number or explicit "ms" → milliseconds
    return num / 1000.0


def exec_action_wait(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute WAIT action."""
    secs = parse_wait_secs(act.args)
    if interp.mode == "dry-run":
        interp.out.step("    ⏳", f"WAIT {secs}s (simulated)")
    elif interp._skip_waits:
        interp.out.step("    ⏳", f"WAIT {secs}s (skipped)")
    else:
        _do_sleep(interp, secs, f"WAIT {secs}s")
    from oqlos.core.base import StepStatus
    return StepStatus.PASSED


def _do_sleep(interp: "CqlInterpreter", secs: float, label: str) -> None:
    """Perform sleep operation."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            interp.out.step("    ⏳", f"{label} (skipped in sync)")
        else:
            loop.run_until_complete(asyncio.sleep(max(secs, 0.0)))
            interp.out.step("    ⏳", label)
    except RuntimeError:
        time.sleep(max(secs, 0.0))
        interp.out.step("    ⏳", label)


def exec_action_min_max(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute MIN/MAX action."""
    sensor = act.target
    op = ">=" if act.kind == "min" else "<="
    try:
        val = float(act.args.split()[0])
    except (ValueError, IndexError):
        val = 0.0

    cond = CqlCondition(sensor=sensor, operator=op, value=val)
    return interp._evaluate_condition(CqlAction(kind="condition", condition=cond))


def exec_action_val(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute VAL action."""
    sensor = act.target
    val = interp.sensor_values.get(sensor)
    if val is None:
        val = interp.vars.get(sensor)
    if val is None:
        val = 0.0
    interp.vars.set(sensor, val)
    interp.out.step("    📊", f"VAL [{sensor}] = {val} {act.args}")
    from oqlos.core.base import StepStatus
    return StepStatus.PASSED


def exec_action_log(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute LOG action."""
    interp.out.info(interp.vars.interpolate(act.args or act.raw))
    from oqlos.core.base import StepStatus
    return StepStatus.PASSED


def exec_action_error(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute ERROR action."""
    message = interp.vars.interpolate(act.args or act.raw)
    interp.errors.append(message)
    interp.out.error(message)
    from oqlos.core.base import StepStatus
    return StepStatus.FAILED


def exec_action_else(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute inline ELSE ERROR/INFO/WARNING action."""
    from oqlos.core.base import StepStatus

    cond = act.condition or CqlCondition()
    severity = (cond.on_fail or "INFO").upper()
    message = interp.vars.interpolate(cond.fail_message or act.args or act.raw)

    if severity == "ERROR":
        interp.errors.append(message)
        interp.out.error(message)
        return StepStatus.FAILED
    if severity == "WARNING":
        interp.warnings.append(message)
        interp.out.warn(message)
        return StepStatus.WARNING

    interp.out.info(message)
    return StepStatus.PASSED


def exec_action_sample(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute SAMPLE action as dry-run sampling metadata."""
    state = (act.method or "").strip().upper() or (act.args.split()[0].upper() if act.args else "START")
    current = interp.sensor_values.get(act.target)
    if current is None:
        current = interp._coerce_float(interp.vars.get(act.target))
    interp.sensor_values.setdefault(act.target, 0.0 if current is None else float(current))
    interp.vars.set(f"sample:{act.target}", state)
    interp.out.step("    🧪", f"SAMPLE {act.target} {act.args or state}")
    from oqlos.core.base import StepStatus
    return StepStatus.PASSED


def _resolve_numeric_token(interp: "CqlInterpreter", token: str) -> float:
    """Resolve a FUNC argument as a numeric literal, variable, or sampled sensor."""
    key = str(token or "").strip()
    if not key:
        return 0.0

    if key in interp.sensor_values:
        return float(interp.sensor_values[key])

    interpolated = interp.vars.interpolate(key)
    numeric = interp._coerce_float(interpolated)
    if numeric is not None:
        return float(numeric)

    value = interp.vars.get(key)
    numeric = interp._coerce_float(value)
    if numeric is not None:
        return float(numeric)

    return 0.0


def _func_avg(values: list[float]) -> float:
    """Calculate average of values."""
    return sum(values) / len(values) if values else 0.0


def _func_sum(values: list[float]) -> float:
    """Calculate sum of values."""
    return sum(values)


def _func_reduce_or_zero(values: list[float], reducer) -> float:
    return reducer(values) if values else 0.0


def _func_sub(values: list[float]) -> float:
    """Subtract remaining values from first value."""
    return values[0] - sum(values[1:]) if values else 0.0


def _func_div(values: list[float], interp: "CqlInterpreter", target: str) -> float:
    """Divide values sequentially with zero check."""
    if not values:
        return 0.0
    result = values[0]
    for divisor in values[1:]:
        if divisor == 0:
            interp.out.warn(f"FUNC {target}: division by zero in dry-run, keeping result at 0")
            return 0.0
        result /= divisor
    return result


def _func_mul(values: list[float]) -> float:
    """Multiply all values."""
    result = 1.0
    for value in values:
        result *= value
    return result


_func_add = _func_sum


# Dispatch table for FUNC handlers: method -> handler function
_FUNC_HANDLERS: dict[str, callable] = {
    "AVG": _func_avg,
    "SUM": _func_sum,
    "MIN": lambda values: _func_reduce_or_zero(values, min),
    "MAX": lambda values: _func_reduce_or_zero(values, max),
    "SUB": _func_sub,
    "DIV": _func_div,
    "MUL": _func_mul,
    "ADD": _func_add,
}


def exec_action_func(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute FUNC action using simple arithmetic over literals and variables."""
    from oqlos.core.base import StepStatus

    method = str(act.method or "").strip().upper()
    tokens = [token.strip() for token in str(act.args or "").split(",") if token.strip()]
    values = [_resolve_numeric_token(interp, token) for token in tokens]

    handler = _FUNC_HANDLERS.get(method)
    if handler is None:
        interp.out.warn(f"Unknown FUNC method: {method}")
        return StepStatus.ERROR

    try:
        if method == "DIV":
            result = handler(values, interp, act.target)
        else:
            result = handler(values)
    except Exception as exc:
        interp.out.error(f"FUNC {act.target} failed: {exc}")
        return StepStatus.ERROR

    interp.vars.set(act.target, result)
    interp.sensor_values[act.target] = result
    interp.out.step("    ∑", f"FUNC {act.target} = {result}")
    return StepStatus.PASSED


def exec_action_goto(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute GOTO action by skipping the rest of the current goal."""
    interp.vars.set("last_goto", act.target)
    interp.out.step("    ↪", f"GOTO {act.target}")
    interp._goal_skipped = True
    from oqlos.core.base import StepStatus
    return StepStatus.PASSED


def exec_action_api(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute API_* action with deterministic dry-run responses."""
    endpoint = interp.vars.interpolate(act.args or "")
    method = str(act.method or "API_GET").upper()
    response = _mock_api_response(interp, endpoint)
    interp.vars.set("api.last.method", method)
    interp.vars.set("api.last.path", endpoint)
    interp.vars.set("api.last.status", 200)
    interp.vars.set("api.last.response", response)
    interp.out.step("    🌐", f"{method} {endpoint} -> 200 (simulated)")
    from oqlos.core.base import StepStatus
    return StepStatus.PASSED


def exec_action_expect(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute EXPECT_* diagnostics as dry-run discovery checks."""
    tokens = _drop_command_token(act)
    label = tokens[0] if tokens else (act.method or "expect")
    _mark_success(interp, label)
    interp.out.step("    🔎", f"{act.method} {', '.join(tokens)} (simulated)")
    from oqlos.core.base import StepStatus
    return StepStatus.PASSED


def _assert_status(interp: "CqlInterpreter", act: CqlAction, tokens: list[str]) -> "StepStatus":
    """Handle ASSERT_STATUS: verify HTTP status code."""
    from oqlos.core.base import StepStatus
    expected = int(_coerce_expected_value(tokens[0] if tokens else 200) or 200)
    actual = int(_coerce_expected_value(interp.vars.get("api.last.status")) or 0)
    if actual != expected:
        return _record_failure(interp, "api.status", f"Expected HTTP {expected}, got {actual}")
    interp.out.step("    ✅", f"ASSERT_STATUS {expected}")
    return StepStatus.PASSED


def _assert_json(interp: "CqlInterpreter", act: CqlAction, tokens: list[str]) -> "StepStatus":
    """Handle ASSERT_JSON: verify JSON path value."""
    from oqlos.core.base import StepStatus
    if len(tokens) < 2:
        return _record_failure(interp, "api.json", f"Malformed ASSERT_JSON: {act.raw}")
    path = tokens[0]
    operator = tokens[1] if len(tokens) > 2 else "=="
    expected = tokens[2] if len(tokens) > 2 else tokens[1]
    actual = _get_nested_value(interp.vars.get("api.last.response") or {}, path)
    if not _compare_values(actual, operator, expected):
        return _record_failure(
            interp,
            path,
            f"ASSERT_JSON {path} {operator} {expected} failed for {actual}",
        )
    interp.out.step("    ✅", f"ASSERT_JSON {path} {operator} {expected}")
    return StepStatus.PASSED


def _assert_sensor(interp: "CqlInterpreter", act: CqlAction, tokens: list[str]) -> "StepStatus":
    """Handle ASSERT_SENSOR: verify sensor condition."""
    from oqlos.core.base import StepStatus
    if len(tokens) < 3:
        return _record_failure(interp, "sensor", f"Malformed ASSERT_SENSOR: {act.raw}")
    sensor, operator, raw_value = tokens[:3]
    unit = tokens[3] if len(tokens) > 3 else ""
    numeric = interp._coerce_float(raw_value)
    cond = CqlCondition(
        sensor=sensor,
        operator=operator,
        value=numeric,
        unit=unit,
        on_fail="ERROR",
        fail_message=f"ASSERT_SENSOR failed: {sensor} {operator} {raw_value}",
    )
    status = interp._evaluate_condition(CqlAction(kind="condition", condition=cond, args=raw_value))
    if status == StepStatus.PASSED:
        _mark_success(interp, sensor)
    else:
        interp.vars.set(f"failure:{sensor}", True)
    return status


def _assert_valve(interp: "CqlInterpreter", act: CqlAction, tokens: list[str]) -> "StepStatus":
    """Handle ASSERT_VALVE: verify valve state."""
    from oqlos.core.base import StepStatus
    if len(tokens) < 2:
        return _record_failure(interp, "valve", f"Malformed ASSERT_VALVE: {act.raw}")
    target, expected_token = tokens[:2]
    actual = _lookup_peripheral_state(interp, target)
    expected = _normalize_bool(expected_token)
    actual_bool = _normalize_bool(actual)
    if expected is None or actual_bool is None or actual_bool != expected:
        return _record_failure(
            interp,
            target,
            f"ASSERT_VALVE {target} expected {expected_token}, got {actual}",
        )
    _mark_success(interp, target)
    interp.out.step("    ✅", f"ASSERT_VALVE {target} == {expected}")
    return StepStatus.PASSED


# Dispatch table for ASSERT handlers: method -> handler function
_ASSERT_HANDLERS: dict[str, callable] = {
    "ASSERT_STATUS": _assert_status,
    "ASSERT_JSON": _assert_json,
    "ASSERT_SENSOR": _assert_sensor,
    "ASSERT_VALVE": _assert_valve,
}


def exec_action_assert(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute ASSERT_* actions for dry-run diagnostics and API checks."""
    from oqlos.core.base import StepStatus

    method = str(act.method or "").upper()
    tokens = _drop_command_token(act)

    handler = _ASSERT_HANDLERS.get(method)
    if handler:
        return handler(interp, act, tokens)

    return _record_failure(interp, method.lower(), f"Unsupported assert action: {act.raw}")


def exec_action_shell(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute shell/export helpers in dry-run mode."""
    tokens = _drop_command_token(act)
    method = str(act.method or "").upper()

    if method == "GET_SENSOR":
        sensor = tokens[0] if tokens else "sensor"
        value = interp.sensor_values.get(sensor)
        if value is None:
            value = {"nc-sensor": 2500.0, "sc-sensor": 2500.0, "wc-sensor": 2500.0}.get(sensor, 1.0)
            interp.sensor_values[sensor] = value
        interp.vars.set(sensor, value)
        interp.out.step("    📡", f"GET_SENSOR {sensor} -> {value}")
        from oqlos.core.base import StepStatus
        return StepStatus.PASSED

    if method == "SAVE_JSON":
        target = tokens[0] if tokens else "json"
        interp.vars.set(target, interp.vars.get("api.last.response") or {})
        interp.out.step("    💾", f"SAVE_JSON {target}")
        from oqlos.core.base import StepStatus
        return StepStatus.PASSED

    if method == "SHELL_EXPORT":
        key = tokens[0] if tokens else "EXPORT"
        value = tokens[1] if len(tokens) > 1 else ""
        exports = interp.vars.get("shell_exports") or {}
        if not isinstance(exports, dict):
            exports = {}
        exports = dict(exports)
        exports[key] = value
        interp.vars.set("shell_exports", exports)
        interp.vars.set(key, value)
        interp.out.step("    🐚", f"SHELL_EXPORT {key}={value}")
        from oqlos.core.base import StepStatus
        return StepStatus.PASSED

    return _record_failure(interp, method.lower(), f"Unsupported shell action: {act.raw}")


def exec_action_var_set(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute VAR assignment action."""
    val = interp.vars.interpolate(act.args)
    interp.vars.set(act.target, val)
    interp.out.step("    📌", f"VAR {act.target} = {val}")
    from oqlos.core.base import StepStatus
    return StepStatus.PASSED


def exec_action_condition(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute condition action."""
    if interp.mode == "execute":
        interp._refresh_sensors_from_firmware()
    return interp._evaluate_condition(act)


def exec_action_if_fail_block(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute IF_FAIL block when a tracked diagnostic target has failed."""
    from oqlos.core.base import StepStatus

    if not bool(interp.vars.get(f"failure:{act.target}")):
        return StepStatus.PASSED

    for sub_act in act.then_actions:
        status = interp._execute_action(sub_act)
        if status not in (StepStatus.PASSED, StepStatus.SKIPPED):
            return status
    return StepStatus.PASSED


def exec_action_if_block(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute IF block action."""
    from oqlos.core.base import StepStatus

    # For basic blocks (nested), stay internal
    if act.then_actions or act.else_actions:
        cond_status = interp._evaluate_condition(act)
        target_actions = act.then_actions if cond_status == StepStatus.PASSED else act.else_actions
        for sub_act in target_actions:
            status = interp._execute_action(sub_act)
            if status not in (StepStatus.PASSED, StepStatus.SKIPPED):
                return status
        return StepStatus.PASSED

    # For Flat DSL - if condition fails, skip the rest of the current goal
    cond_status = interp._evaluate_condition(act)
    if cond_status != StepStatus.PASSED:
        interp.out.info(f"Condition not met: {act.raw} — skipping rest of goal")
        interp._goal_skipped = True

    return StepStatus.PASSED


def exec_action_loop_block(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute LOOP block action."""
    from oqlos.core.base import StepStatus, VariableStore

    method = act.method or "times"
    interp.out.step("    🔄", f"LOOP {method.upper()}: {act.raw}")
    interp._loop_break = False

    max_iters = 1000
    iteration = 0

    # Create scoped variable store for loop
    old_vars = interp.vars
    interp.vars = VariableStore(parent=old_vars)

    try:
        if method == "times":
            count = int(act.args) if act.args.isdigit() else 1
            for i in range(count):
                interp.vars.set("ITER", i)  # Expose current iteration
                for sub_act in act.loop_actions:
                    status = interp._execute_action(sub_act)
                    if getattr(interp, "_loop_break", False):
                        interp._loop_break = False
                        return StepStatus.PASSED
                    if status not in (StepStatus.PASSED, StepStatus.SKIPPED):
                        return status
            return StepStatus.PASSED

        if method == "while":
            while interp._evaluate_condition(act) == StepStatus.PASSED:
                iteration += 1
                if iteration > max_iters:
                    interp.out.error(f"Loop safety limit reached ({max_iters} iters)")
                    return StepStatus.ERROR

                for sub_act in act.loop_actions:
                    status = interp._execute_action(sub_act)
                    if getattr(interp, "_loop_break", False):
                        interp._loop_break = False
                        return StepStatus.PASSED
                    if status not in (StepStatus.PASSED, StepStatus.SKIPPED):
                        return status
            return StepStatus.PASSED
    finally:
        interp.vars = old_vars

    return StepStatus.PASSED


def exec_action_endloop(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute REPEAT STOP as a break for the current loop."""
    from oqlos.core.base import StepStatus

    interp._loop_break = True
    interp.out.step("    🔚", "REPEAT STOP")
    return StepStatus.PASSED


def exec_action_set(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute SET action with intelligent dispatch."""
    from oqlos.core.base import StepStatus

    value = interp.vars.interpolate((act.args or "").strip())
    target_lower = (act.target or "").strip().lower()
    interp.vars.set(act.target, value)

    motor2_status = _try_exec_motor2_set(interp, target_lower, value)
    if motor2_status is not None:
        return motor2_status

    if target_lower in {"wait", "delay", "pause", "timeout"}:
        return _exec_set_wait(interp, act, value)

    if interp.mode == "execute":
        if interp._resolve_peripheral_id(act.target or "") is not None:
            result = interp._exec_set_peripheral(act, value)
            if result is not None:
                return result
    interp.out.step("    ⚙️", _format_set_command(act.target, value))
    return StepStatus.PASSED



def _exec_set_wait(interp: "CqlInterpreter", act: CqlAction, value: str) -> "StepStatus":
    """Handle SET wait/delay/pause/timeout."""
    from oqlos.core.base import StepStatus

    secs = parse_wait_secs(value)
    if interp.mode == "dry-run":
        interp.out.step("    ⏳", f"{_format_set_command(act.target, value)} (simulated)")
    elif interp._skip_waits:
        interp.out.step("    ⏳", f"{_format_set_command(act.target, value)} (skipped)")
    else:
        _do_sleep(interp, secs, _format_set_command(act.target, value))
    return StepStatus.PASSED


def exec_action_action(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute generic ACTION."""
    from oqlos.core.base import StepStatus

    args_interpolated = interp.vars.interpolate(act.args)
    if interp.mode == "execute":
        return interp._execute_firmware_action(act, args_interpolated)
    interp.out.step("    →", f"{act.target}.{act.method} {args_interpolated}")
    return StepStatus.PASSED


# Action dispatch table mapping action kinds to handler functions
ACTION_HANDLERS = {
    "action": exec_action_action,
    "task": exec_action_task,
    "set": exec_action_set,
    "save": exec_action_save,
    "wait": exec_action_wait,
    "min": exec_action_min_max,
    "max": exec_action_min_max,
    "val": exec_action_val,
    "log": exec_action_log,
    "error": exec_action_error,
    "else": exec_action_else,
    "sample": exec_action_sample,
    "func": exec_action_func,
    "goto": exec_action_goto,
    "api": exec_action_api,
    "expect": exec_action_expect,
    "assert": exec_action_assert,
    "shell": exec_action_shell,
    "condition": exec_action_condition,
    "if_else": exec_action_condition,
    "if_block": exec_action_if_block,
    "if_fail_block": exec_action_if_fail_block,
    "loop_block": exec_action_loop_block,
    "endloop": exec_action_endloop,
    "var_set": exec_action_var_set,
}
