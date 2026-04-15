"""
Action handlers for CQL Interpreter.

Extracted from interpreter.py to reduce god module complexity.
Each handler is a focused function with CC<10.
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from oqlos.models.dsl_models import CqlAction, CqlCondition

if TYPE_CHECKING:
    from oqlos.core.interpreter import CqlInterpreter
    from oqlos.core.base import StepStatus


def exec_action_task(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute TASK action."""
    args_interpolated = interp.vars.interpolate(act.args)
    interp.out.step("    🔨", args_interpolated)
    from oqlos.core.base import StepStatus
    return StepStatus.PASSED


def exec_action_save(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute SAVE action."""
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
    val = interp.sensor_values.get(sensor, 0.0)
    interp.vars.set(sensor, val)
    interp.out.step("    📊", f"VAL [{sensor}] = {val} {act.args}")
    from oqlos.core.base import StepStatus
    return StepStatus.PASSED


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
                    if status not in (StepStatus.PASSED, StepStatus.SKIPPED):
                        return status
            return StepStatus.PASSED
    finally:
        interp.vars = old_vars

    return StepStatus.PASSED


def exec_action_set(interp: "CqlInterpreter", act: CqlAction) -> "StepStatus":
    """Execute SET action with intelligent dispatch."""
    from oqlos.core.base import StepStatus

    value = interp.vars.interpolate((act.args or "").strip())
    target_lower = (act.target or "").strip().lower()
    interp.vars.set(act.target, value)

    if target_lower in {"wait", "delay", "pause", "timeout"}:
        return _exec_set_wait(interp, act, value)

    if interp.mode == "execute":
        if interp._resolve_peripheral_id(act.target or "") is not None:
            result = interp._exec_set_peripheral(act, value)
            if result is not None:
                return result
    interp.out.step("    ⚙️", f"SET [{act.target}] = [{value}]")
    return StepStatus.PASSED


def _exec_set_wait(interp: "CqlInterpreter", act: CqlAction, value: str) -> "StepStatus":
    """Handle SET wait/delay/pause/timeout."""
    from oqlos.core.base import StepStatus

    secs = parse_wait_secs(value)
    if interp.mode == "dry-run":
        interp.out.step("    ⏳", f"SET [{act.target}] = [{value}] (simulated)")
    elif interp._skip_waits:
        interp.out.step("    ⏳", f"SET [{act.target}] = [{value}] (skipped)")
    else:
        _do_sleep(interp, secs, f"SET [{act.target}] = [{value}]")
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
    "condition": exec_action_condition,
    "if_else": exec_action_condition,
    "if_block": exec_action_if_block,
    "loop_block": exec_action_loop_block,
    "var_set": exec_action_var_set,
}
