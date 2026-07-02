"""File editor service for managing and executing OQL scenarios."""

from __future__ import annotations

import logging
import os
import pathlib
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from oqlos.shared.file_ops import (
    PathEscapeError,
    _ensure_safe_path,
    iter_entries,
    read_file,
    write_file,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/editor", tags=["editor"])


def _default_scenarios_dir() -> pathlib.Path:
    """Locate the repository ``scenarios/`` directory.

    Honours the ``OQLOS_SCENARIOS_DIR`` env var so deployments can point
    at an external library, and falls back to ``<repo>/scenarios`` (one
    level above the ``oqlos`` Python package).
    """
    override = os.environ.get("OQLOS_SCENARIOS_DIR")
    if override:
        return pathlib.Path(override)
    return pathlib.Path(__file__).resolve().parents[2] / "scenarios"


SCENARIOS_DIR = _default_scenarios_dir()


class FileInfo(BaseModel):
    name: str
    path: str
    size: int
    is_directory: bool


class FileContent(BaseModel):
    path: str
    content: str


class ExecutionRequest(BaseModel):
    scenario_file: str
    mode: str = "real"
    speed: float = 1.0


def _normalize_oql_mode(mode: str) -> str:
    raw = (mode or "").strip().lower().replace("_", "-")
    if raw in {"", "real", "execute", "run"}:
        return "execute"
    if raw in {"dry-run", "dryrun", "simulation", "simulate", "mock"}:
        return "dry-run"
    if raw in {"validate", "validation"}:
        return "validate"
    return raw


def _result_dict(result: Any) -> dict[str, Any]:
    return result if isinstance(result, dict) else {}


def _editor_response_from_oql(
    *,
    scenario_file: str,
    response: Any,
) -> dict[str, Any]:
    result = _result_dict(getattr(response, "result", None))
    ok = bool(getattr(response, "ok", False))
    error = getattr(response, "error", None)
    errors = list(result.get("errors") or [])
    if error and error not in errors:
        errors.append(str(error))
    steps = result.get("steps") if isinstance(result.get("steps"), list) else []
    return {
        "status": "success" if ok else "error",
        "ok": ok,
        "scenario_name": result.get("source") or result.get("scenario_name") or scenario_file,
        "steps_executed": result.get("total", len(steps)),
        "duration_ms": result.get("duration_ms"),
        "errors": errors,
        "warnings": list(result.get("warnings") or []),
        "node_id": getattr(response, "node_id", ""),
        "result": result or None,
    }


def _safe_path(file_path: str) -> pathlib.Path:
    """Resolve file_path within SCENARIOS_DIR, raising HTTP 403 on escape."""
    try:
        return _ensure_safe_path(SCENARIOS_DIR, file_path)
    except PathEscapeError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/files")
async def list_files() -> dict[str, Any]:
    """List all entries in the scenarios directory."""
    try:
        entries = [
            FileInfo(**entry)
            for entry in iter_entries(SCENARIOS_DIR)
        ]
        return {"files": sorted(entries, key=lambda x: (not x.is_directory, x.name))}
    except Exception as e:
        logger.error("Error listing files: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/file/{file_path:path}")
async def read_file_endpoint(file_path: str) -> FileContent:
    """Read a file's content."""
    try:
        content = read_file(SCENARIOS_DIR, file_path)
        return FileContent(path=file_path, content=content)
    except (FileNotFoundError, IsADirectoryError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except PathEscapeError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except Exception as e:
        logger.error("Error reading file: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/file/{file_path:path}")
async def write_file_endpoint(file_path: str, file_content: FileContent) -> dict[str, str]:
    """Write content to a file (creates parent directories as needed)."""
    try:
        write_file(SCENARIOS_DIR, file_path, file_content.content)
        return {"status": "success", "path": file_path}
    except PathEscapeError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except Exception as e:
        logger.error("Error writing file: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


def _sensor_telemetry_recorder():
    """Build an on_sensors_observed callback bound to the shared event store.

    Best-effort: returns None when no StateManager is initialised (e.g. CLI
    or test contexts), so real-hardware runs get an audit trail without
    forcing every CqlInterpreter caller to depend on oqlos.core.cqrs.
    """
    from oqlos.api.utils import execution_ctrl as _ctrl
    from oqlos.core.cqrs.telemetry import record_sensor_readings

    state_manager = _ctrl.state_manager
    if state_manager is None:
        return None
    return lambda readings: record_sensor_readings(state_manager.event_store, readings)


@router.post("/execute")
async def execute_scenario(request: ExecutionRequest) -> dict[str, Any]:
    """Execute a scenario file using oqlos runtime."""
    try:
        from oqlos.api.oql_mqtt import get_oql_controller

        full_path = _safe_path(request.scenario_file)
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Scenario file not found")

        content = full_path.read_text(encoding="utf-8")
        oql_mode = _normalize_oql_mode(request.mode)
        skip_waits = request.speed > 2.0
        controller = get_oql_controller()
        if controller is not None:
            response = await controller.execute(
                content,
                kind="script",
                mode=oql_mode,
                skip_waits=skip_waits,
                timeout=max(15.0, min(300.0, 60.0 * max(request.speed, 1.0))),
                source="editor",
            )
            return _editor_response_from_oql(
                scenario_file=request.scenario_file,
                response=response,
            )

        from oqlos.core.interpreter import CqlInterpreter

        interpreter = CqlInterpreter(
            mode=oql_mode,
            quiet=False,
            skip_waits=skip_waits,
            on_sensors_observed=_sensor_telemetry_recorder(),
        )
        doc = interpreter.parse(content, request.scenario_file)
        result = interpreter.execute(doc)

        return {
            "status": "success",
            "ok": result.ok,
            "scenario_name": doc.metadata.scenario_name or request.scenario_file,
            "steps_executed": len(result.steps),
            "duration_ms": result.duration_ms,
            "errors": result.errors,
            "warnings": result.warnings,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error executing scenario: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
