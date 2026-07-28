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
_DEFAULT_LOG_MAX_BYTES = 10_000_000
_DEFAULT_LOG_BACKUP_COUNT = 5


def _bounded_env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    """Read an integer logging limit without making a bad env break startup."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return max(minimum, min(int(raw), maximum))
    except ValueError:
        return default


def _logging_level(name: str | None, default: int) -> int:
    return getattr(logging, str(name or "").strip().upper(), default)


def configure_oqlos_logging(*, force: bool = False) -> None:
    """
    Configure root logging for oqlos-server.

    - Default: INFO to stderr (systemd journal when run as oqlos-hardware-api.service).
    - Optional rotating file: set OQLOS_LOG_FILE=/path/to/oqlos-hardware-api.log
    - Rotation: OQLOS_LOG_MAX_BYTES (10 MB), OQLOS_LOG_BACKUP_COUNT (5)
    - Noisy HTTP client loggers default to WARNING; override with
      OQLOS_HTTP_CLIENT_LOG_LEVEL when debugging transport details.
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
    level = _logging_level(level_name, logging.INFO)
    max_bytes = _bounded_env_int(
        "OQLOS_LOG_MAX_BYTES",
        int(settings.log_max_bytes or _DEFAULT_LOG_MAX_BYTES),
        minimum=100_000,
        maximum=1_000_000_000,
    )
    backup_count = _bounded_env_int(
        "OQLOS_LOG_BACKUP_COUNT",
        int(settings.log_backup_count or _DEFAULT_LOG_BACKUP_COUNT),
        minimum=1,
        maximum=50,
    )

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
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
        )

    logging.basicConfig(
        level=level,
        format=_LOG_FORMAT,
        handlers=handlers,
        force=True,
    )
    http_client_level = _logging_level(
        os.getenv("OQLOS_HTTP_CLIENT_LOG_LEVEL")
        or str(settings.http_client_log_level or "WARNING"),
        logging.WARNING,
    )
    for logger_name in ("httpx", "httpcore"):
        logging.getLogger(logger_name).setLevel(http_client_level)
    _CONFIGURED = True
    root = logging.getLogger("oqlos")
    root.info(
        "OqlOS logging configured level=%s handlers=%s",
        level_name,
        [type(handler).__name__ for handler in handlers],
    )
    if log_file:
        root.info(
            "OqlOS rotating log file=%s max_bytes=%s backup_count=%s",
            Path(log_file).expanduser(),
            max_bytes,
            backup_count,
        )


def get_logger(name: str | None = None) -> logging.Logger:
    if not _CONFIGURED:
        configure_oqlos_logging()
    if _nfo_get_logger is not None:
        return _nfo_get_logger(name)
    return logging.getLogger(name or "oqlos")


__all__ = ["configure_oqlos_logging", "get_logger"]
