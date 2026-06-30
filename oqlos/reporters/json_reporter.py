"""OQLos JSON reporter — produces data.json for report rendering pipelines.

Pipeline:  test.oql + Python runtime  →  data.json  →  raport.html (JS)

The output JSON conforms to the OQLos Report Schema consumed by both the
backend HTML generator (``oqlctl report``) and the frontend ``OqlReportRenderer``.

Usage (programmatic):
    from oqlos.reporters.json_reporter import report_json
    json_str = report_json(script_result)
    Path("data.json").write_text(json_str)

Usage (CLI):
    oqlctl run scenario.oql --report json > data.json
    oqlctl report data.json -o report.html
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oqlos.core.base import ScriptResult, StepResult


def _step_to_dict(step: "StepResult") -> dict:
    """Serialise a single StepResult to the report schema."""
    d: dict = {
        "name": step.name,
        "status": step.status.value,
        "duration_ms": round(step.duration_ms, 1),
    }
    if step.message:
        d["message"] = step.message
    if step.value is not None:
        d["value"] = step.value
    if step.details:
        # Propagate threshold / CHECK data
        for key in ("min", "max", "unit", "sensor", "condition",
                     "pass_message", "fail_message", "parameter"):
            if key in step.details:
                d[key] = step.details[key]
    return d


def _group_steps_into_goals(steps: list) -> "list[dict]":
    """Group StepResult list into goal dicts, splitting on GOAL: header steps."""
    goals: list[dict] = []
    current_goal: dict | None = None
    for step in steps:
        if step.name.upper().startswith("GOAL:") or step.name.upper().startswith("GOAL "):
            goal_name = step.name.split(":", 1)[-1].strip() if ":" in step.name else step.name[5:].strip()
            current_goal = {"name": goal_name, "steps": [], "thresholds": []}
            goals.append(current_goal)
            continue
        if current_goal is None:
            current_goal = {"name": "Default", "steps": [], "thresholds": []}
            goals.append(current_goal)
        current_goal["steps"].append(_step_to_dict(step))
    return goals


def _collect_thresholds(goals: "list[dict]") -> None:
    """Populate threshold lists for each goal in-place."""
    for goal in goals:
        params: dict[str, dict] = {}
        for s in goal["steps"]:
            param = s.get("parameter") or s.get("sensor")
            if not param:
                continue
            if param not in params:
                params[param] = {"parameter": param}
            for key in ("min", "max", "unit"):
                if key in s:
                    params[param][key] = s[key]
        goal["thresholds"] = list(params.values())


def _extract_metadata(variables: dict) -> "tuple[dict, dict]":
    """Extract metadata fields from variables dict. Returns (metadata, remaining_vars)."""
    vars_copy = dict(variables) if variables else {}
    metadata = {
        "device_type": vars_copy.pop("DEVICE_TYPE", ""),
        "device_model": vars_copy.pop("DEVICE_MODEL", ""),
        "manufacturer": vars_copy.pop("MANUFACTURER", ""),
    }
    return metadata, vars_copy


def report_json(result: "ScriptResult", *, pretty: bool = True) -> str:
    """Format a ScriptResult as the canonical ``data.json`` for report rendering.

    Schema::
        {
          "$schema": "oqlos-report-v1",
          "generated_at": "ISO-8601",
          "scenario": { "source", "ok", "duration_ms", "passed", "failed", "total" },
          "metadata": { "device_type", "device_model", "manufacturer" },
          "goals": [
            {
              "name": "Goal Name",
              "steps": [
                { "name", "status", "duration_ms", "value?", "message?",
                  "min?", "max?", "unit?", "pass_message?", "fail_message?" }
              ],
              "thresholds": [ { "parameter", "min?", "max?", "unit?" } ]
            }
          ],
          "variables": {},
          "errors": [],
          "warnings": []
        }
    """
    goals = _group_steps_into_goals(result.steps)
    _collect_thresholds(goals)
    metadata, variables = _extract_metadata(result.variables)

    payload = {
        "$schema": "oqlos-report-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario": {
            "source": result.source,
            "ok": result.ok,
            "duration_ms": round(result.duration_ms, 1),
            "passed": result.passed,
            "failed": result.failed,
            "total": len(result.steps),
        },
        "metadata": metadata,
        "goals": goals,
        "variables": variables,
        "errors": result.errors,
        "warnings": result.warnings,
    }

    return json.dumps(payload, indent=2 if pretty else None, ensure_ascii=False)
