# shared/logger.py
"""Shared logger accessor with a stable exported symbol for static analysis."""

from __future__ import annotations

import logging
from typing import Callable

_nfo_get_logger: Callable[[str | None], logging.Logger] | None

try:
    from nfo import get_logger as _nfo_get_logger
except ImportError:
    _nfo_get_logger = None


def get_logger(name: str | None = None) -> logging.Logger:
    if _nfo_get_logger is not None:
        return _nfo_get_logger(name)
    return logging.getLogger(name)


__all__ = ["get_logger"]
