# shared/nfo_config_factory.py
"""
Shared nfo configuration factory — eliminates duplication across services.

Replaces identical nfo_config.py files in:
- firmware/nfo_config.py
- dsl/nfo_config.py
- services/backend/fleet-data-manager/nfo_config.py
- services/backend/fleet-workshop-manager/nfo_config.py

Usage:
    from oqlos.shared.config_factory import create_nfo_setup

    setup_nfo = create_nfo_setup(
        service_name="c2004-firmware",
        nfo_env_default="firmware",
        auto_log_modules=["main", "services.state_manager"],
        bridge_modules=["firmware", "uvicorn"],
    )
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from oqlos.shared.release_version import resolve_release_version
from oqlos.shared.logs_query import resolve_logs_db_path as _resolve_logs_db_path


def create_nfo_setup(
    *,
    service_name: str,
    nfo_env_default: str,
    auto_log_modules: list[str],
    bridge_modules: list[str],
    project_root_fallback: Path | None = None,
) -> Callable[[], None]:
    """Factory that creates a service-specific setup_nfo() function.

    Follows Open/Closed Principle — new services configure via parameters,
    no need to copy the entire nfo_config.py file.

    Args:
        service_name: nfo logger name (e.g. "c2004-firmware")
        nfo_env_default: default NFO_ENV value (e.g. "firmware")
        auto_log_modules: modules to auto-instrument with @log_call
        bridge_modules: stdlib loggers to bridge into nfo sinks
        project_root_fallback: fallback project root for logs.db resolution
    """
    _initialized = False

    def setup_nfo() -> None:
        nonlocal _initialized
        if _initialized:
            return
        try:
            from nfo import configure, auto_log_by_name
        except ImportError:
            return

        fallback = project_root_fallback or Path(__file__).parent.parent
        db_path = _resolve_logs_db_path(fallback)

        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        nfo_level = os.environ.get("NFO_LEVEL", "DEBUG")
        nfo_env = os.environ.get("NFO_ENV", nfo_env_default)
        service_version = os.environ.get("SERVICE_VERSION") or resolve_release_version(fallback)

        configure(
            name=service_name,
            level=nfo_level,
            sinks=[f"sqlite:{db_path}"],
            modules=bridge_modules,
            environment=nfo_env,
            version=service_version,
        )

        auto_log_by_name(*auto_log_modules, level="DEBUG")
        _initialized = True

    return setup_nfo
