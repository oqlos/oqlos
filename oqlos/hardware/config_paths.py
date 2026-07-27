"""Helpers for resolving the canonical OqlOS configuration file path."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_oqlos_config_path(config_path: str | Path | None = None) -> Path:
    """Resolve the canonical OqlOS hardware configuration path.

    Resolution order:
    1) explicit ``config_path`` argument
    2) ``OQLOS_CONFIG_PATH`` env var
    3) current working directory ``./oqlos.{oql,yaml,json}``
    4) repository root ``<repo>/oqlos.{oql,yaml,json}``

    Raises:
        FileNotFoundError: when no existing file can be resolved.
    """
    if config_path is not None:
        explicit = Path(config_path)
        if explicit.exists():
            return explicit
        raise FileNotFoundError(f"Config file not found: {explicit}")

    env_path = os.getenv("OQLOS_CONFIG_PATH")
    candidates: list[Path] = []
    if env_path:
        candidates.append(Path(env_path))

    for root in (Path.cwd(), Path(__file__).resolve().parents[2]):
        candidates.extend(root / name for name in ("oqlos.oql", "oqlos.yaml", "oqlos.yml", "oqlos.json"))

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "OqlOS configuration not found (checked OQLOS_CONFIG_PATH, cwd, and repo root for OQL/YAML/JSON)"
    )
