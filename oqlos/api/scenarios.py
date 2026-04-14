# firmware/api/scenarios.py
from typing import Any
from fastapi import APIRouter, HTTPException
import httpx

from oqlos.models.scenario import Scenario, Goal, Step
from oqlos.api.utils import execution_ctrl as _ctrl

router = APIRouter(prefix="/api/v1/scenarios", tags=["scenarios"])

@router.get("")
async def get_scenarios():
    """Get all scenarios"""
    return list(_ctrl.state_manager.scenarios.values())

@router.get("/{scenario_id}")
async def get_scenario(scenario_id: str):
    """Get specific scenario"""
    # Guard: if path captured 'fetch' due to param route precedence, delegate to fetch endpoint
    if scenario_id == 'fetch':
        return await fetch_scenarios()
    if scenario_id not in _ctrl.state_manager.scenarios:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return _ctrl.state_manager.scenarios[scenario_id]

async def _fetch_raw_from_sources(sources: list[str]) -> Any | None:
    """Try each URL in order and return the first valid JSON response, or None."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            for src in sources:
                try:
                    resp = await client.get(src)
                    return resp.json()
                except Exception:  # noqa: BLE001
                    continue
    except Exception:  # noqa: BLE001
        pass
    return None

def _compute_slug(item: dict[str, Any], display_name: str, sid: str) -> str | None:
    """Compute a URL-friendly slug from the scenario row fields."""
    tmp_slug = str(item.get("slug") or "").strip()
    if tmp_slug:
        return tmp_slug
    sbase = (item.get("code") or display_name or sid)
    s = "".join(ch.lower() if ch.isalnum() else '-' for ch in str(sbase))
    while '--' in s:
        s = s.replace('--', '-')
    return s.strip('-') or None

def _extract_id(item: dict[str, Any]) -> str | None:
    """Extract and validate scenario ID from a raw row. Returns None if missing."""
    sid = str(item.get("id") or "").strip()
    return sid or None

def _extract_display_fields(item: dict[str, Any], sid: str) -> dict[str, Any]:
    """Resolve display name, description, device, protocol, code, slug from raw row."""
    display_name = str(item.get("name") or item.get("title") or item.get("code") or sid)
    return {
        "name": display_name,
        "description": str(item.get("description") or ""),
        "device": str(item.get("device") or item.get("device_id") or ""),
        "protocol": str(item.get("protocol") or item.get("protocol_id") or ""),
        "code": str(item.get("code") or "") or None,
        "slug": _compute_slug(item, display_name, sid),
    }

def _extract_goals(item: dict[str, Any]) -> list[Goal]:
    """Parse goals from the row's content field."""
    content = item.get("content")
    if content is None:
        return []
    return _parse_content_to_goals(content)

def _normalize_scenario_row(item: dict[str, Any]) -> Scenario | None:
    """Convert a raw backend row dict into a Scenario, or None if invalid."""
    sid = _extract_id(item)
    if not sid:
        return None
    fields = _extract_display_fields(item, sid)
    goals = _extract_goals(item)
    return Scenario(id=sid, goals=goals, **fields)

@router.get("/fetch")
async def fetch_scenarios(source: str = "http://localhost:8100/connect-data/test-scenarios"):
    """Fetch scenarios from backend DB or external JSON and normalize shape.
    On failure, return in-memory sample scenarios instead of 500.
    """
    sources = [
        source,
        "http://localhost:8101/api/v1/data/test_scenarios",
        "http://localhost:8100/api/v1/data/test_scenarios",
        "http://localhost:8000/api/v1/data/test_scenarios",
    ]
    raw = await _fetch_raw_from_sources(sources)
    if raw is None:
        return list(_ctrl.state_manager.scenarios.values())

    rows = raw.get("rows") if isinstance(raw, dict) else raw
    out = []
    if isinstance(rows, list):
        for item in rows:
            if not isinstance(item, dict):
                continue
            scenario = _normalize_scenario_row(item)
            if not scenario:
                continue
            # Don't overwrite local scenarios with goals - they are authoritative
            if scenario.id in _ctrl.state_manager.scenarios:
                existing = _ctrl.state_manager.scenarios[scenario.id]
                if existing.goals:
                    out.append(existing.model_dump())
                    continue
            _ctrl.state_manager.scenarios[scenario.id] = scenario
            out.append(scenario.model_dump())
    return out

def _parse_content_to_goals(content) -> list[Goal]:
    """Parse scenario content to extract goals with steps"""
    goals = []
    if isinstance(content, dict) and 'goals' in content:
        for goal_data in content['goals']:
            steps = []
            expectedResult = ""
            validationCriteria = []
            
            if 'steps' in goal_data:
                for step_data in goal_data['steps']:
                    step = Step(
                        id=step_data.get('id', f"step-{len(steps)}"),
                        action=step_data.get('action', 'UNKNOWN'),
                        peripheral=step_data.get('peripheral'),
                        value=step_data.get('value'),
                        duration=step_data.get('duration'),
                        condition=step_data.get('condition')
                    )
                    steps.append(step)
            
            goals.append(Goal(
                id=goal_data.get('id', f"goal-{len(goals)}"),
                name=goal_data.get('name', 'Unnamed Goal'),
                description=goal_data.get('description', ''),
                steps=steps,
                expectedResult=expectedResult,
                validationCriteria=validationCriteria,
            ))
    return goals

def _ensure_list(x) -> list:
    """Wrap a scalar in a list; pass through lists; return [] for None."""
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]

def _normalize_dsl_payload(payload: dict[str, Any]) -> list[dict]:
    """Normalize the various accepted register-dsl payload shapes into a list of item dicts."""
    scenarios_input = payload.get('scenarios')
    if scenarios_input is None:
        scenarios_input = [payload]
    if not isinstance(scenarios_input, list):
        raise HTTPException(status_code=400, detail="Invalid payload: 'scenarios' must be a list or provide single scenario fields")
    return [item for item in scenarios_input if isinstance(item, dict)]

def _collect_dsl_strings(item: dict[str, Any]) -> list[str]:
    """Gather DSL text entries from 'dsl' and 'goalsDsl' fields."""
    out: list[str] = []
    out.extend([str(x) for x in _ensure_list(item.get('dsl')) if isinstance(x, (str, bytes))])
    out.extend([str(x) for x in _ensure_list(item.get('goalsDsl')) if isinstance(x, (str, bytes))])
    return out

def _parse_goals_from_dsl(goals_dsl: list[str], sid: str, parse_fn) -> list[Goal]:
    """Parse a list of DSL strings into Goal objects with unique IDs."""
    parsed: list[Goal] = []
    idx = 0
    for dsl in goals_dsl:
        try:
            g = parse_fn(dsl, sid)
            if g:
                idx += 1
                g.id = f"goal-runtime-{sid}-{idx}"
                parsed.append(g)
        except Exception:  # noqa: BLE001
            continue
    return parsed

def _merge_goals_into_scenario(sid: str, item: dict[str, Any], parsed_goals: list[Goal]) -> None:
    """Merge parsed goals into an existing scenario or create a new one."""
    scenario = _ctrl.state_manager.scenarios.get(sid)
    if scenario:
        scenario.goals = (scenario.goals or []) + parsed_goals
        _ctrl.state_manager.scenarios[sid] = scenario
    else:
        _ctrl.state_manager.scenarios[sid] = Scenario(
            id=sid,
            name=str(item.get('name') or sid),
            description=str(item.get('description') or ''),
            device=str(item.get('device') or ''),
            protocol=str(item.get('protocol') or ''),
            code=None,
            slug=None,
            goals=parsed_goals
        )

def _register_single_dsl_scenario(item: dict[str, Any], parse_fn) -> str | None:
    """Parse DSL strings from one payload item and merge into _ctrl.state_manager.
    Returns the scenario id on success, or None."""
    sid = str(item.get('id') or item.get('scenarioId') or '').strip()
    if not sid:
        return None
    goals_dsl = _collect_dsl_strings(item)
    if not goals_dsl:
        return None
    parsed_goals = _parse_goals_from_dsl(goals_dsl, sid, parse_fn)
    if not parsed_goals:
        return None
    _merge_goals_into_scenario(sid, item, parsed_goals)
    return sid

@router.post("/register-dsl")
async def register_dsl(payload: dict[str, Any]):
    """Register one or many scenarios defined as DSL strings.
    Accepted shapes:
    - {"id": "ts-c20", "name": "C20", "dsl": "GOAL: ..."}
    - {"id": "ts-c20", "name": "C20", "goalsDsl": ["GOAL: ...", "GOAL: ..."]}
    - {"scenarios": [ {"id": "...", "dsl": "..."}, ... ]}
    """
    # Import inside handler to avoid circular import at module import time
    try:
        from oqlos.core.parser import parse_dsl_to_goal  # type: ignore
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Parser unavailable: {ex}")

    items = _normalize_dsl_payload(payload)
    registered = []
    for item in items:
        sid = _register_single_dsl_scenario(item, parse_dsl_to_goal)
        if sid:
            registered.append(sid)
    return {"registered": len(registered), "ids": registered}
