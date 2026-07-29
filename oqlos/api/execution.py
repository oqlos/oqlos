# firmware/api/execution.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json
import asyncio
from typing import Any
from pydantic import ValidationError

from oqlos.errors import OqlosError
from oqlos.models.execution import ExecutionRequest
from oqlos.models.scenario import Step
from oqlos.api.utils import execution_ctrl as _ctrl

router = APIRouter(prefix="/api/v1/execution", tags=["execution"])


def _execution_request_error(reason: str, *, stage: str) -> OqlosError:
    return OqlosError(
        code="api_execution_request_invalid",
        status_code=422,
        detail={
            "architecture": "SOA",
            "layer": "oqlos",
            "component": "scenario-execution",
            "stage": stage,
            "problem_source": "request",
            "operation_id": "execution.api",
            "reason": reason,
        },
    )


def _scenario_not_found(*, operation_id: str) -> OqlosError:
    return OqlosError(
        code="api_scenario_not_found",
        status_code=404,
        detail={
            "architecture": "SOA",
            "layer": "oqlos",
            "component": "scenario-execution",
            "stage": "scenario.lookup",
            "problem_source": "request",
            "operation_id": operation_id,
        },
    )


def _execution_not_found(*, operation_id: str) -> OqlosError:
    return OqlosError(
        code="api_execution_not_found",
        status_code=404,
        detail={
            "architecture": "SOA",
            "layer": "oqlos",
            "component": "scenario-execution",
            "stage": "execution.lookup",
            "problem_source": "request",
            "operation_id": operation_id,
        },
    )

def _resolve_step_label(scenario_id: str, goal_id: str | None, step_id: str | None) -> str | None:
    """Look up the human-readable label for a step within a scenario.
    Returns None when the step cannot be found."""
    if not scenario_id or not step_id:
        return None
    sc = _ctrl.state_manager.scenarios.get(scenario_id)
    if not sc:
        return None
    for g in (sc.goals or []):
        if g.id == (goal_id or ''):
            for s in (g.steps or []):
                if s.id == step_id:
                    return getattr(s, 'label', None)
    return None

def _flatten_steps_for_scenario(scenario_id: str | None) -> list[Step]:
    """Helper function to flatten scenario steps"""
    out: list[Step] = []
    if not scenario_id:
        return out
    sc = _ctrl.state_manager.scenarios.get(scenario_id)
    if not sc or not isinstance(sc.goals, list):
        return out
    for g in sc.goals:
        if not isinstance(g.steps, list):
            continue
        out.extend(g.steps)
    return out

def _build_step_labels(sc) -> list[str]:
    """Build a flat list of human-readable step labels from a scenario."""
    labels: list[str] = []
    if not sc:
        return labels
    for g in sc.goals:
        for s in g.steps:
            label = getattr(s, 'label', None)
            if not label:
                label = f"{s.action}"
                if s.peripheral:
                    label = f"{label} [{s.peripheral}]"
            labels.append(label)
    return labels

def _resolve_current_index(exec_obj, sc) -> int:
    """Determine the current step index from orchestrator state or by scanning goals."""
    current_idx = getattr(_ctrl.orchestrator, 'current_index', -1)
    if current_idx is not None and current_idx >= 0:
        return current_idx
    if not exec_obj or not sc:
        return -1
    idx = 0
    for g in sc.goals:
        for s in (g.steps or []):
            if g.id == exec_obj.currentGoal and s.id == exec_obj.currentStep:
                return idx
            idx += 1
    return -1

def _current_projection() -> dict[str, Any]:
    """Get current execution projection"""
    exec_obj = _ctrl.orchestrator.current_execution
    status = exec_obj.status if exec_obj else 'idle'
    progress = exec_obj.progress if exec_obj else 0
    scenario_id = exec_obj.scenarioId if exec_obj else ''

    sc = _ctrl.state_manager.scenarios.get(scenario_id) if scenario_id else None
    return {
        'status': status,
        'progress': progress,
        'steps': _build_step_labels(sc),
        'currentIndex': _resolve_current_index(exec_obj, sc),
        'scenarioId': scenario_id,
    }

@router.post("/start")
async def start_execution(request: ExecutionRequest):
    """Start scenario execution"""
    inline_dsl = request.content.get('dsl') if request.content else None
    if inline_dsl:
        try:
            _register_dsl_scenario(request.scenarioId, request.content['dsl'])
        except ValueError as exc:
            raise _execution_request_error("dsl_invalid", stage="dsl.validate") from exc

    if request.scenarioId not in _ctrl.state_manager.scenarios:
        if inline_dsl:
            raise _execution_request_error("dsl_invalid", stage="dsl.validate")
        raise _scenario_not_found(operation_id="execution.start")

    execution_id = await _ctrl.orchestrator.execute_scenario(
        scenario_id=request.scenarioId,
        goals=request.goals,
        mode=request.mode,
        speed=request.speed
    )
    return {"executionId": execution_id, "status": "started"}

@router.post("/step")
async def execute_step(payload: dict[str, Any]):
    """Execute a single DSL step within the current (or new) execution.

    Expected payload::
        {
            "scenarioId": "scn-xxx",
            "step": { "action": "SET", "peripheral": "P1", "value": 100, ... },
            "executionId": "optional-existing-id"
        }
    """
    scenario_id = payload.get("scenarioId")
    step_data = payload.get("step", {})
    execution_id = payload.get("executionId")

    if not scenario_id or not step_data:
        raise _execution_request_error("step_fields_required", stage="step.validate")

    # If no active execution, start one implicitly
    if execution_id and execution_id in _ctrl.state_manager.executions:
        exec_obj = _ctrl.state_manager.executions[execution_id]
    elif _ctrl.orchestrator.current_execution:
        exec_obj = _ctrl.orchestrator.current_execution
        execution_id = exec_obj.executionId
    else:
        if scenario_id not in _ctrl.state_manager.scenarios:
            raise _scenario_not_found(operation_id="execution.step")
        execution_id = await _ctrl.orchestrator.execute_scenario(
            scenario_id=scenario_id,
            goals=[],
            mode="step",
            speed=1.0,
        )
        exec_obj = _ctrl.state_manager.executions.get(execution_id)

    # Build a Step model and delegate to orchestrator
    try:
        step = Step(
            id=step_data.get("id", "step-inline"),
            action=step_data.get("action", "NOP"),
            peripheral=step_data.get("peripheral"),
            value=step_data.get("value"),
        )
    except ValidationError as exc:
        raise _execution_request_error("step_invalid", stage="step.validate") from exc
    result = await _ctrl.orchestrator.execute_single_step(step) if hasattr(_ctrl.orchestrator, 'execute_single_step') else {"status": "executed", "step": step_data}

    return {
        "executionId": execution_id,
        "status": "step_executed",
        "result": result,
    }

def _register_dsl_scenario(scenario_id: str, dsl_content: str):
    """Parse DSL content and register as a temporary scenario.
    Delegates to the canonical parser in utils/dsl_parser.py.
    """
    from oqlos.models.scenario import Scenario
    from oqlos.core.parser import parse_dsl_to_goal_with_issues

    goal, invalid_lines = parse_dsl_to_goal_with_issues(dsl_content, scenario_id)
    if invalid_lines:
        joined = '; '.join(invalid_lines[:5])
        raise ValueError(f'invalid runtime DSL lines: {joined}')
    if goal:
        scenario = Scenario(
            id=scenario_id,
            name=f"Runtime Scenario {scenario_id}",
            description="Dynamically loaded from frontend DSL",
            device="runtime-simulator",
            protocol="oql",
            code=dsl_content,
            slug=scenario_id,
            goals=[goal]
        )
        _ctrl.state_manager.scenarios[scenario_id] = scenario

def _make_exec_route(ctrl_fn):
    """Factory for pause/resume/stop routes — eliminates 3 near-identical handlers."""
    async def handler(execution_id: str):
        if execution_id not in _ctrl.state_manager.executions:
            raise _execution_not_found(operation_id="execution.control-by-id")
        return ctrl_fn(execution_id)
    handler.__name__ = ctrl_fn.__name__
    handler.__doc__ = f"{ctrl_fn.__name__.replace('do_', '').capitalize()} execution"
    return handler

pause_execution  = router.post("/{execution_id}/pause")(_make_exec_route(_ctrl.do_pause))
resume_execution = router.post("/{execution_id}/resume")(_make_exec_route(_ctrl.do_resume))
stop_execution   = router.post("/{execution_id}/stop")(_make_exec_route(_ctrl.do_stop))

@router.get("/by-id/{execution_id}")
async def get_execution(execution_id: str):
    """Get execution status"""
    execution = _ctrl.state_manager.executions.get(execution_id)
    if execution is None:
        raise _execution_not_found(operation_id="execution.get")
    return execution

@router.get("/projection")
async def get_execution_projection():
    """Return a lightweight execution projection used by the frontend polling fallback."""
    return _current_projection()

@router.get("/status")
async def get_execution_status():
    """Return textual logs and status for polling fallback when SSE is unavailable."""
    exec_obj = _ctrl.orchestrator.current_execution
    if not exec_obj:
        return {
            "status": "idle",
            "logs": ["No active execution."]
        }
    
    # Simple logs placeholder
    logs = [
        f"Status: {exec_obj.status}",
        f"Progress: {exec_obj.progress:.1f}%"
    ]
    if exec_obj.currentGoal:
        logs.append(f"Current Goal: {exec_obj.currentGoal}")
    if exec_obj.currentStep:
        logs.append(f"Current Step: {exec_obj.currentStep}")
    
    return {
        "status": exec_obj.status,
        "logs": logs
    }

@router.get("/logs")
async def get_execution_logs():
    """Return execution logs for frontend polling."""
    exec_obj = _ctrl.orchestrator.current_execution
    if not exec_obj:
        return {
            "logs": [],
            "status": "idle"
        }
    
    logs = []
    if exec_obj.status:
        logs.append(f"[{exec_obj.status.upper()}] Execution active")
    if exec_obj.currentGoal:
        logs.append(f"Goal: {exec_obj.currentGoal}")
    if exec_obj.currentStep:
        logs.append(f"Step: {exec_obj.currentStep}")
    if exec_obj.progress > 0:
        logs.append(f"Progress: {exec_obj.progress:.1f}%")
    
    return {
        "logs": logs,
        "status": exec_obj.status
    }

# Legacy control endpoints without execution_id (frontend fallback)
def _make_legacy_route(ctrl_fn):
    async def handler():
        if not _ctrl.orchestrator.current_execution:
            raise OqlosError(
                code="api_execution_state_conflict",
                status_code=409,
                detail={
                    "architecture": "SOA",
                    "layer": "oqlos",
                    "component": "scenario-execution",
                    "stage": "state.validate",
                    "problem_source": "runtime-state",
                    "operation_id": "execution.control-current",
                },
            )
        return ctrl_fn()
    handler.__name__ = f"{ctrl_fn.__name__}_legacy"
    return handler

pause_execution_legacy  = router.post("/pause")(_make_legacy_route(_ctrl.do_pause))
resume_execution_legacy = router.post("/resume")(_make_legacy_route(_ctrl.do_resume))
stop_execution_legacy   = router.post("/stop")(_make_legacy_route(_ctrl.do_stop))

# ============= Streaming Endpoints =============

@router.get("/stream")
async def execution_stream(scenario: str | None = None):
    """Stream execution events for frontend polling fallback"""
    async def generate_stream():
        yield f"data: {json.dumps({'type': 'connection', 'status': 'connected'})}\n\n"
        
        # Stream current projection every 1 second
        for i in range(30):  # Stream for 30 seconds max
            projection = _current_projection()
            if scenario:
                projection['requestedScenario'] = scenario
            
            event_data = {
                'type': 'projection_update',
                'data': projection,
                'timestamp': f"{i}s"
            }
            
            yield f"data: {json.dumps(event_data)}\n\n"
            await asyncio.sleep(1)
        
        yield f"data: {json.dumps({'type': 'stream_end', 'message': 'Stream completed'})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

@router.get("/logs/stream")
async def execution_logs_stream(scenario: str | None = None):
    """Stream execution logs for terminal view"""
    async def generate_logs():
        scenario_name = scenario or "all"
        yield f"data: {json.dumps({'type': 'log', 'message': f'🔗 Connected to logs stream for scenario: {scenario_name}'})}\n\n"
        
        # Get current execution logs
        exec_obj = _ctrl.orchestrator.current_execution
        if exec_obj:
            # Resolve current step label if available
            step_label = _resolve_step_label(exec_obj.scenarioId, exec_obj.currentGoal, exec_obj.currentStep)
            initial_logs = [
                f"▶️ Execution started: {exec_obj.executionId}",
                f"📋 Scenario: {exec_obj.scenarioId}",
                f"🎯 Current Goal: {exec_obj.currentGoal or 'None'}",
                f"📍 Current Step: {exec_obj.currentStep or 'None'}" + (f" — {step_label}" if step_label else ""),
                f"📊 Progress: {exec_obj.progress:.1f}%",
                f"🔄 Status: {exec_obj.status}"
            ]
            
            for log in initial_logs:
                yield f"data: {json.dumps({'type': 'log', 'message': log, 'timestamp': 'now'})}\n\n"
                await asyncio.sleep(0.1)
        else:
            yield f"data: {json.dumps({'type': 'log', 'message': '⏸️ No active execution', 'timestamp': 'now'})}\n\n"
        
        # Stream periodic updates for 30 seconds
        for i in range(30):
            if _ctrl.orchestrator.current_execution:
                exec_obj = _ctrl.orchestrator.current_execution
                log_message = f"⏱️ {i+1}s - Status: {exec_obj.status} | Progress: {exec_obj.progress:.1f}%"
                
                if exec_obj.currentStep:
                    step_label = _resolve_step_label(exec_obj.scenarioId, exec_obj.currentGoal, exec_obj.currentStep)
                    log_message += f" | Step: {exec_obj.currentStep}" + (f" — {step_label}" if step_label else "")
                
                yield f"data: {json.dumps({'type': 'log', 'message': log_message, 'timestamp': f'{i+1}s'})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'log', 'message': f'⏸️ {i+1}s - No active execution', 'timestamp': f'{i+1}s'})}\n\n"
            
            await asyncio.sleep(1)
        
        yield f"data: {json.dumps({'type': 'log', 'message': '🔚 Log stream ended', 'timestamp': 'end'})}\n\n"
    
    return StreamingResponse(
        generate_logs(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
