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


def _load_checkout_implementation():
    """Load the submodule fallback used by source checkouts without an install."""
    canonical = (
        Path(__file__).resolve().parents[2]
        / "packages"
        / "backend-shared-py"
        / "src"
        / "shared"
        / "logs_query.py"
    )
    if not canonical.is_file():  # pragma: no cover - invalid source checkout
        raise ImportError(
            "Brak pakietu c2004-backend-shared ani jego źródła "
            f"({canonical}). Uruchom: git submodule update --init "
            "packages/backend-shared-py"
        )

    spec = importlib.util.spec_from_file_location(
        "oqlos.shared._logs_query_impl",
        canonical,
    )
    if spec is None or spec.loader is None:  # pragma: no cover - importlib guard
        raise ImportError(f"Nie można załadować kanonicznego logs_query: {canonical}")
    implementation = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = implementation
    spec.loader.exec_module(implementation)
    return implementation


try:
    from shared import logs_query as _impl
except ImportError:
    _impl = _load_checkout_implementation()

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
