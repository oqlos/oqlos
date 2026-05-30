# shared/logger.py
"""OqlOS logging setup — stderr/journal plus optional log file."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable

_nfo_get_logger: Callable[[str | None], logging.Logger] | None

try:
    from nfo import get_logger as _nfo_get_logger
except ImportError:
    _nfo_get_logger = None

_CONFIGURED = False
_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_oqlos_logging(*, force: bool = False) -> None:
    """
    Configure root logging for oqlos-server.

    - Default: INFO to stderr (systemd journal when run as oqlos-hardware-api.service).
    - Optional file: set OQLOS_LOG_FILE=/path/to/oqlos-hardware-api.log
    - Level: OQLOS_LOG_LEVEL=DEBUG
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    from oqlos.config import get_settings

    settings = get_settings()
    level_name = (
        os.getenv("OQLOS_LOG_LEVEL")
        or os.getenv("LOG_LEVEL")
        or str(settings.log_level or "INFO")
    ).upper()
    level = getattr(logging, level_name, logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    log_file = (
        os.getenv("OQLOS_LOG_FILE")
        or os.getenv("OQLOS_HARDWARE_LOG_FILE")
        or str(settings.log_file or "")
    ).strip()
    if log_file:
        path = Path(log_file).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                path,
                maxBytes=2_000_000,
                backupCount=3,
                encoding="utf-8",
            )
        )

    logging.basicConfig(
        level=level,
        format=_LOG_FORMAT,
        handlers=handlers,
        force=True,
    )
    _CONFIGURED = True
    root = logging.getLogger("oqlos")
    root.info(
        "OqlOS logging configured level=%s handlers=%s",
        level_name,
        [type(handler).__name__ for handler in handlers],
    )
    if log_file:
        root.info("OqlOS log file: %s", Path(log_file).expanduser())


def get_logger(name: str | None = None) -> logging.Logger:
    if not _CONFIGURED:
        configure_oqlos_logging()
    if _nfo_get_logger is not None:
        return _nfo_get_logger(name)
    return logging.getLogger(name or "oqlos")


__all__ = ["configure_oqlos_logging", "get_logger"]
