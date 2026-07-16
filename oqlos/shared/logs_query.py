# shared/logs_query.py
"""Shim — kanoniczna implementacja żyje w repo oqlos/backend-shared-py
(submodule ``packages/backend-shared-py``), współdzielonym z c2004.

Public API (bez zmian):
    from oqlos.shared.logs_query import LogsQueryService, resolve_logs_db_path

Wersja kanoniczna jest nadzbiorem dawnej lokalnej kopii (dodatkowo
``PostgresLogsQueryService`` i ``build_logs_query_service``); klasa SQLite
ma identyczne zachowanie (parity AST poza nazwanymi stałymi limitów).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CANONICAL = (
    Path(__file__).resolve().parents[2]
    / "packages" / "backend-shared-py" / "src" / "shared" / "logs_query.py"
)

if not _CANONICAL.is_file():  # pragma: no cover — niezainicjowany submodule
    raise ImportError(
        f"Brak kanonicznego logs_query ({_CANONICAL}). "
        "Uruchom: git submodule update --init packages/backend-shared-py"
    )

_spec = importlib.util.spec_from_file_location("oqlos.shared._logs_query_impl", _CANONICAL)
_impl = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _impl
_spec.loader.exec_module(_impl)

LogsQueryService = _impl.LogsQueryService
PostgresLogsQueryService = _impl.PostgresLogsQueryService
build_logs_query_service = _impl.build_logs_query_service
resolve_logs_db_path = _impl.resolve_logs_db_path

__all__ = [
    "LogsQueryService",
    "PostgresLogsQueryService",
    "build_logs_query_service",
    "resolve_logs_db_path",
]
