"""Optional data-source routes used by the legacy state API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from oqlos.api.utils import execution_ctrl as _ctrl
from oqlos.shared.http_fallback import fetch_first_json

router = APIRouter()


def _normalize_variables_payload(payload: object) -> list[Any] | None:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return payload["rows"]
    return None


@router.get("/api/v1/variables")
async def get_variables_alias() -> list[Any]:
    """Return variables using the same optional-source fallback as fetch."""
    return await fetch_variables()


@router.get("/api/v1/variables/fetch")
async def fetch_variables(
    source: str = "http://localhost:8101/api/v1/data/variables",
) -> list[Any]:
    """Fetch the peripheral state table, returning [] when sources are offline."""
    sources = [
        source,
        "http://localhost:8101/api/v1/data/variables",
        "http://localhost:8100/api/v1/data/variables",
        "http://localhost:8000/api/v1/data/variables",
    ]
    result = await fetch_first_json(
        sources,
        _normalize_variables_payload,
        timeout_seconds=3.0,
    )
    return result or []


def _normalize_protocol_steps_payload(payload: object) -> dict[str, list[Any]] | None:
    if isinstance(payload, dict) and isinstance(payload.get("steps"), list):
        return {"steps": payload["steps"]}
    if isinstance(payload, list):
        return {"steps": payload}
    return None


@router.get("/api/v1/protocol-steps/fetch")
async def fetch_protocol_steps(
    scenario: str,
    source: str = "http://localhost:8100/connect-test/protocol-steps",
) -> dict[str, list[Any]]:
    """Fetch protocol steps, preferring the locally loaded scenario."""
    if scenario and scenario in _ctrl.state_manager.scenarios:
        local = _ctrl.state_manager.scenarios[scenario]
        return {
            "steps": [
                {
                    "step": step.id,
                    "action": step.action,
                    "peripheral": step.peripheral,
                    "value": step.value,
                    "duration": step.duration,
                    "condition": step.condition,
                }
                for goal in local.goals
                for step in goal.steps
            ]
        }

    sources = [
        f"{source}?scenario={scenario}",
        f"http://localhost:8101/api/v1/data/protocol-steps?scenario={scenario}",
    ]
    result = await fetch_first_json(
        sources,
        _normalize_protocol_steps_payload,
        timeout_seconds=3.0,
    )
    return result or {"steps": []}


__all__ = [
    "fetch_protocol_steps",
    "fetch_variables",
    "get_variables_alias",
    "router",
]
