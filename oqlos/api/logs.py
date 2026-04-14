# firmware/api/logs.py
"""
Lightweight nfo logs query endpoint for firmware service.
Reads from the shared db/logs/logs.db SQLite database.

Refactored: delegates to shared/logs_query.py (DRY, SRP).
"""
import sys
from pathlib import Path

from fastapi import APIRouter, Query

# Ensure shared/ is importable
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from oqlos.shared.logs_query import LogsQueryService, resolve_logs_db_path

router = APIRouter(prefix="/api/v1/logs", tags=["logs"])

def _get_service() -> LogsQueryService:
    db_path = resolve_logs_db_path(Path(__file__).parent.parent.parent)
    return LogsQueryService(db_path)

@router.get("")
async def get_logs(
    level: str | None = Query(None, description="Filter by level: DEBUG, INFO, WARNING, ERROR"),
    function: str | None = Query(None, description="Filter by function name (partial)"),
    module: str | None = Query(None, description="Filter by module name (partial)"),
    q: str | None = Query(None, description="Full-text search"),
    environment: str | None = Query(None, description="Filter by environment tag"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Browse nfo logs from shared SQLite database."""
    return _get_service().query_logs(
        level=level, function=function, module=module,
        q=q, environment=environment, limit=limit, offset=offset,
    )

@router.get("/stats")
async def get_log_stats():
    """Summary statistics from logs database."""
    return _get_service().get_stats()
