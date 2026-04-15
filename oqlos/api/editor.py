"""File editor service for managing and executing OQL scenarios"""

from __future__ import annotations

import logging
import os
import pathlib
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/editor", tags=["editor"])

SCENARIOS_DIR = pathlib.Path("/home/tom/github/oqlos/oqlos/oqlos/scenarios")


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
    mode: str = "mock"
    speed: float = 1.0


def _ensure_safe_path(file_path: str) -> pathlib.Path:
    """Ensure the file path is within the scenarios directory"""
    full_path = (SCENARIOS_DIR / file_path).resolve()
    if not str(full_path).startswith(str(SCENARIOS_DIR.resolve())):
        raise HTTPException(status_code=403, detail="Access denied: path outside scenarios directory")
    return full_path


@router.get("/files")
async def list_files() -> dict[str, Any]:
    """List all files in the scenarios directory"""
    try:
        files = []
        for item in SCENARIOS_DIR.iterdir():
            relative_path = item.relative_to(SCENARIOS_DIR)
            files.append(FileInfo(
                name=item.name,
                path=str(relative_path),
                size=item.stat().st_size if item.is_file() else 0,
                is_directory=item.is_dir()
            ))
        return {"files": sorted(files, key=lambda x: (not x.is_directory, x.name))}
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file/{file_path:path}")
async def read_file(file_path: str) -> FileContent:
    """Read a file's content"""
    try:
        full_path = _ensure_safe_path(file_path)
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        if full_path.is_dir():
            raise HTTPException(status_code=400, detail="Path is a directory")
        
        content = full_path.read_text(encoding="utf-8")
        return FileContent(path=file_path, content=content)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/file/{file_path:path}")
async def write_file(file_path: str, file_content: FileContent) -> dict[str, str]:
    """Write content to a file"""
    try:
        full_path = _ensure_safe_path(file_path)
        
        # Create parent directories if they don't exist
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        full_path.write_text(file_content.content, encoding="utf-8")
        return {"status": "success", "path": file_path}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error writing file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_scenario(request: ExecutionRequest) -> dict[str, Any]:
    """Execute a scenario file using oqlos runtime"""
    try:
        from oqlos.core.interpreter import CqlInterpreter
        
        # Read the scenario file
        full_path = _ensure_safe_path(request.scenario_file)
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Scenario file not found")
        
        content = full_path.read_text(encoding="utf-8")
        
        # Create interpreter with appropriate mode
        interpreter = CqlInterpreter(
            mode="dry-run" if request.mode == "mock" else "execute",
            quiet=False,
            skip_waits=request.speed > 2.0
        )
        
        # Parse and execute the scenario
        doc = interpreter.parse(content, request.scenario_file)
        result = interpreter.execute(doc)
        
        return {
            "status": "success",
            "ok": result.ok,
            "scenario_name": doc.metadata.scenario_name or request.scenario_file,
            "steps_executed": len(result.steps),
            "duration_ms": result.duration_ms,
            "errors": result.errors,
            "warnings": result.warnings
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing scenario: {e}")
        raise HTTPException(status_code=500, detail=str(e))
