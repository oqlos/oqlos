# firmware/api/state.py
import logging
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
import asyncio
import math
import time
from datetime import datetime, timezone
from typing import Any

from oqlos.models.execution import ExecutionRequest, CommandEnvelope
from oqlos.models.scenario import Scenario
from oqlos.core.parser import parse_dsl_to_goal_with_issues
from oqlos.api.utils import execution_ctrl as _ctrl
from oqlos.api.state_sources import (
    fetch_protocol_steps,
    fetch_variables,
    get_variables_alias,
    router as state_sources_router,
)
from oqlos.errors import OqlosError

router = APIRouter(tags=["state"])
router.include_router(state_sources_router)
logger = logging.getLogger(__name__)

def _compose_named_state() -> dict[str, Any]:
    """Build peripheral state as named dictionary"""
    named = {}
    for pid, per in _ctrl.state_manager.peripherals.items():
        # Sanitize key names for safe access
        safe_key = pid.replace('-', '_').replace('.', '_')
        named[safe_key] = {
            'id': per.id,
            'type': per.type,
            'name': per.name,
            'currentValue': per.currentValue,
            'targetValue': per.targetValue,
            'unit': per.unit,
            'status': per.status,
            'mode': per.mode
        }
    return named

def _compose_sim_state_list(named_state: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert named state to sim state list format"""
    out = []
    
    # Add peripheral parameters
    for k, v in named_state.items():
        out.append({
            'type': 'parameter',
            'name': k, 
            'value': v.get('currentValue', 0)
        })
    
    # Add functions (placeholder for now)
    functions = {
        'system_pressure': 0,
        'leak_rate': 0,
        'safety_check': True
    }
    
    for k, v in functions.items():
        out.append({'type': 'function', 'name': k, 'value': v})
    
    return out

@router.get("/api/v1/state")
async def get_state():
    """Get current system state"""
    named = _compose_named_state()
    return named

# ============= Value Streaming (SSE) =============

async def _generate_sinusoidal_values(
    param: str = "pressure",
    min_val: float = 2.0,
    max_val: float = 11.0,
    period: float = 10.0,
    interval: float = 0.1
):
    """
    SSE generator for sinusoidal demo values.
    Period: time for one complete sine cycle (default 10 seconds)
    Interval: time between value updates (default 100ms)
    """
    start_time = time.time()
    amplitude = (max_val - min_val) / 2
    offset = min_val + amplitude
    
    while True:
        elapsed = time.time() - start_time
        # Sinusoidal value: offset + amplitude * sin(2π * t / period)
        value = offset + amplitude * math.sin(2 * math.pi * elapsed / period)
        
        event_data = {
            "type": "value_update",
            "param": param,
            "value": round(value, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed": round(elapsed, 2),
            "period": period,
            "demo": True
        }
        
        yield f"data: {__import__('json').dumps(event_data)}\n\n"
        await asyncio.sleep(interval)

@router.get("/api/v1/values/stream")
async def stream_values(
    param: str = "pressure",
    min: float = 2.0,
    max: float = 11.0,
    period: float = 10.0,
    interval: float = 0.1,
    demo: bool = True
):
    """
    SSE endpoint for live value streaming.
    
    In demo mode: generates sinusoidal values with specified period.
    In real mode: would stream actual sensor values.
    
    Query params:
    - param: parameter name (default: "pressure")
    - min: minimum value (default: 2.0)
    - max: maximum value (default: 11.0)
    - period: sinusoid period in seconds (default: 10.0)
    - interval: update interval in seconds (default: 0.1)
    - demo: use demo sinusoidal generator (default: true)
    """
    return StreamingResponse(
        _generate_sinusoidal_values(param, min, max, period, interval),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no"
        }
    )

@router.get("/api/v1/values/current")
async def get_current_value(param: str = "pressure"):
    """
    Get current value for a parameter (single request, not streaming).
    Returns the current sinusoidal demo value or sensor reading.
    """
    # For demo, return current sinusoidal value
    elapsed = time.time() % 10.0  # Use 10s period
    min_val, max_val = 2.0, 11.0
    amplitude = (max_val - min_val) / 2
    offset = min_val + amplitude
    value = offset + amplitude * math.sin(2 * math.pi * elapsed / 10.0)
    
    return {
        "param": param,
        "value": round(value, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "demo": True
    }

@router.get("/api/v1/sim/state")
async def get_sim_state():
    """Get simulation state in list format"""
    named = _compose_named_state()
    return _compose_sim_state_list(named)

def _maybe_register_dsl_from_content(data: dict, scenario_id: str):
    """If the command data contains inline DSL content, parse and register it."""
    dsl = _extract_inline_dsl(data)
    if not isinstance(dsl, str) or not dsl.strip():
        return None, []
    logger.debug("Parsing inline DSL content length=%d", len(dsl))
    try:
        parsed_goal, invalid_lines = parse_dsl_to_goal_with_issues(dsl, scenario_id)
        if parsed_goal:
            temp = Scenario(
                id=scenario_id,
                name='Runtime scenario from frontend',
                description='Dynamically created from DSL',
                device='',
                protocol='',
                goals=[parsed_goal]
            )
            _ctrl.state_manager.scenarios[scenario_id] = temp
            logger.debug("Created temporary scenario with %d steps", len(parsed_goal.steps))
            return parsed_goal, invalid_lines
    except (TypeError, ValueError):
        logger.warning("Inline DSL failed request validation")
        return None, ["invalid_dsl"]
    return None, []


def _extract_scenario_id(data: dict[str, Any]) -> str:
    """Normalize scenario identifiers from frontend and CLI payloads."""
    candidates = [
        data.get('scenarioId'),
        data.get('scenario'),
        data.get('scenario_id'),
        data.get('scenario_context_id'),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ''


def _extract_inline_dsl(data: dict[str, Any]) -> str | None:
    """Normalize inline DSL payloads from frontend and CLI calls."""
    content = data.get('content')
    if isinstance(content, dict):
        dsl = content.get('dsl') or content.get('dsl_code')
        if isinstance(dsl, str) and dsl.strip():
            return dsl

    for key in ('dsl', 'dsl_code'):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _execution_request_error(reason: str, *, stage: str) -> OqlosError:
    """Build a typed request failure without reflecting command or DSL input."""
    return OqlosError(
        code="api_execution_request_invalid",
        status_code=422,
        detail={
            "architecture": "SOA",
            "layer": "oqlos",
            "component": "scenario-execution",
            "stage": stage,
            "problem_source": "request",
            "operation_id": "execution.command",
            "reason": reason,
        },
    )

async def _handle_start(env: CommandEnvelope) -> dict:
    data = env.data or {}
    scenario_id = _extract_scenario_id(data)
    inline_dsl = _extract_inline_dsl(data)
    if not scenario_id and inline_dsl:
        scenario_id = f"runtime-{int(datetime.now(timezone.utc).timestamp() * 1000)}"

    req = ExecutionRequest(
        scenarioId=scenario_id,
        goals=data.get('goals') or None,
        mode=str(data.get('mode') or 'auto'),
        speed=float(data.get('speed') or 1.0),
    )
    logger.debug("StartExecution request: scenario=%s, goals=%s, mode=%s", req.scenarioId, req.goals, req.mode)

    if not req.scenarioId:
        raise _execution_request_error("source_required", stage="source.validate")

    parsed_goal, invalid_lines = _maybe_register_dsl_from_content(data, req.scenarioId)
    if invalid_lines:
        raise _execution_request_error("dsl_invalid", stage="dsl.validate")

    if inline_dsl and parsed_goal and not parsed_goal.steps:
        raise _execution_request_error("dsl_empty", stage="dsl.validate")

    if req.scenarioId not in _ctrl.state_manager.scenarios:
        raise OqlosError(
            code="api_scenario_not_found",
            status_code=404,
            detail={
                "architecture": "SOA",
                "layer": "oqlos",
                "component": "scenario-execution",
                "stage": "scenario.lookup",
                "problem_source": "request",
                "operation_id": "execution.start",
            },
        )

    execution_id = f"exec-{datetime.now(timezone.utc).timestamp()}"

    async def run_execution():
        try:
            logger.info("Background task STARTED for scenario: %s", req.scenarioId)
            result = await _ctrl.orchestrator.execute_scenario(
                scenario_id=req.scenarioId,
                goals=req.goals,
                mode=req.mode,
                speed=req.speed,
            )
            logger.info("Background task COMPLETED. Result: %s", result)
        except Exception as exc:  # noqa: BLE001 - background task isolation boundary
            logger.error(
                "Background scenario execution failed exception_type=%s",
                type(exc).__name__,
            )

    task = asyncio.create_task(run_execution())
    logger.debug("Async execution task created: %s", task)
    return {"executionId": execution_id, "status": "started"}

def _make_state_handler(ctrl_fn):
    """Factory for pause/resume/stop command handlers — eliminates 3 near-identical blocks."""
    async def handler(env: CommandEnvelope) -> dict:
        orchestrator = _ctrl.get_orchestrator()
        if not orchestrator.current_execution:
            raise OqlosError(
                code="api_execution_state_conflict",
                status_code=409,
                detail={
                    "architecture": "SOA",
                    "layer": "oqlos",
                    "component": "scenario-execution",
                    "stage": "state.validate",
                    "problem_source": "runtime-state",
                    "operation_id": "execution.control",
                },
            )
        return ctrl_fn()
    handler.__name__ = f"_handle_{ctrl_fn.__name__}"
    return handler

_handle_pause  = _make_state_handler(_ctrl.do_pause)
_handle_resume = _make_state_handler(_ctrl.do_resume)
_handle_stop   = _make_state_handler(_ctrl.do_stop)

_COMMAND_HANDLERS: dict[str, Any] = {
    'StartExecution': _handle_start,
    'PauseExecution': _handle_pause,
    'ResumeExecution': _handle_resume,
    'StopExecution': _handle_stop,
}

__all__ = [
    "fetch_protocol_steps",
    "fetch_variables",
    "get_variables_alias",
    "router",
]

@router.post("/api/v1/commands")
async def post_commands(env: CommandEnvelope, background_tasks: BackgroundTasks):
    """Command bus endpoint used by frontend.
    Supports: StartExecution, PauseExecution, ResumeExecution, StopExecution.
    """
    cmd = (env.command or '').strip()
    logger.debug("Received command: %s", cmd)
    handler = _COMMAND_HANDLERS.get(cmd)
    if not handler:
        raise _execution_request_error("command_unsupported", stage="command.resolve")
    return await handler(env)
