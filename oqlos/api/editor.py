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
    """Locate the ``scenarios/`` directory shipped with the package.

    Honours the ``OQLOS_SCENARIOS_DIR`` env var so deployments can point
    at an external library, and falls back to ``oqlos/scenarios`` next to
    this package — the same directory used by ``oqlos.core._oql_adapter``.
    """
    override = os.environ.get("OQLOS_SCENARIOS_DIR")
    if override:
        return pathlib.Path(override)
    return pathlib.Path(__file__).resolve().parent.parent / "scenarios"


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


@router.post("/execute")
async def execute_scenario(request: ExecutionRequest) -> dict[str, Any]:
    """Execute a scenario file using oqlos runtime."""
    try:
        from oqlos.core.interpreter import CqlInterpreter

        full_path = _safe_path(request.scenario_file)
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Scenario file not found")

        content = full_path.read_text(encoding="utf-8")
        interpreter = CqlInterpreter(
            mode="execute",
            quiet=False,
            skip_waits=request.speed > 2.0,
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
