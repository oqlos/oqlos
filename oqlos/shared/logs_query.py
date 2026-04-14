# shared/logs_query.py
"""
Shared nfo logs query logic — eliminates duplication across services.

Replaces identical query logic in:
- firmware/api/logs.py
- services/backend/fleet-data-manager/app/api/v1/endpoints/logs.py
- services/backend/fleet-workshop-manager/app/api/v1/endpoints/logs.py

Usage:
    from oqlos.shared.logs_query import LogsQueryService, resolve_logs_db_path

    svc = LogsQueryService(resolve_logs_db_path(project_root))
    result = svc.query_logs(level="ERROR", limit=50)
    stats = svc.get_stats()
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any


def resolve_logs_db_path(project_root_fallback: Path) -> str:
    """Resolve logs.db path from environment or default.

    Shared logic previously duplicated in 4+ logs endpoint files.
    """
    url = os.environ.get("LOG_DATABASE_URL", "")
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    project_root = Path(os.environ.get("PROJECT_ROOT", str(project_root_fallback)))
    return str(project_root / "db" / "logs" / "logs.db")


class LogsQueryService:
    """Read-only query service for nfo logs SQLite database.

    Follows CQRS read-side pattern — pure queries, no side effects.
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    @property
    def db_exists(self) -> bool:
        return Path(self.db_path).exists()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def query_logs(
        self,
        *,
        level: str | None = None,
        function: str | None = None,
        module: str | None = None,
        q: str | None = None,
        environment: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Query logs with filtering, pagination. Returns dict ready for API response."""
        if not self.db_exists:
            return {"rows": [], "total": 0, "db_path": self.db_path, "exists": False}

        conditions: list[str] = []
        params: list[Any] = []

        if level:
            conditions.append("level = ?")
            params.append(level.upper())
        if function:
            conditions.append("function_name LIKE ?")
            params.append(f"%{function}%")
        if module:
            conditions.append("module LIKE ?")
            params.append(f"%{module}%")
        if environment:
            conditions.append("environment = ?")
            params.append(environment)
        if q:
            conditions.append(
                "(function_name LIKE ? OR module LIKE ? OR args LIKE ? OR return_value LIKE ? OR exception LIKE ?)"
            )
            params.extend([f"%{q}%"] * 5)

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""

        conn = self._connect()
        try:
            total_row = conn.execute(f"SELECT COUNT(*) FROM logs{where}", params).fetchone()
            total = total_row[0] if total_row else 0

            rows = conn.execute(
                f"SELECT * FROM logs{where} ORDER BY id DESC LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()

            return {
                "rows": [dict(r) for r in rows],
                "total": total,
                "limit": limit,
                "offset": offset,
                "db_path": self.db_path,
                "exists": True,
            }
        except Exception as e:
            return {"rows": [], "total": 0, "db_path": self.db_path, "exists": True, "error": str(e)}
        finally:
            conn.close()

    def get_stats(self) -> dict[str, Any]:
        """Summary statistics from logs database."""
        if not self.db_exists:
            return {"exists": False, "db_path": self.db_path}

        conn = self._connect()
        try:
            total = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
            errors = conn.execute("SELECT COUNT(*) FROM logs WHERE level = 'ERROR'").fetchone()[0]
            by_level = conn.execute(
                "SELECT level, COUNT(*) as count FROM logs GROUP BY level ORDER BY count DESC"
            ).fetchall()
            by_module = conn.execute(
                "SELECT module, COUNT(*) as count FROM logs GROUP BY module ORDER BY count DESC LIMIT 20"
            ).fetchall()
            latest = conn.execute("SELECT timestamp FROM logs ORDER BY id DESC LIMIT 1").fetchone()

            return {
                "exists": True,
                "db_path": self.db_path,
                "total": total,
                "errors": errors,
                "by_level": {r["level"]: r["count"] for r in by_level},
                "top_modules": {r["module"]: r["count"] for r in by_module},
                "latest_timestamp": latest["timestamp"] if latest else None,
            }
        except Exception as e:
            return {"exists": True, "db_path": self.db_path, "error": str(e)}
        finally:
            conn.close()
