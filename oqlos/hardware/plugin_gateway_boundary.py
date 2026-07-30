"""Typed, sanitized failure helpers for the plugin hardware gateway."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from oqlos.errors.c2004_catalog_generated import CATALOG

PLUGIN_OPERATION_ERRORS = (OSError, RuntimeError, ValueError, httpx.HTTPError)
CONFIGURATION_ERRORS = (OSError, RuntimeError, ValueError)


def plugin_command_failure(reason: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": "Hardware plugin operation failed",
        "reason": reason,
    }


def normalize_plugin_command_result(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return plugin_command_failure("invalid-plugin-response")
    if result.get("success") is False:
        failure = plugin_command_failure("command-rejected")
        error_code = str(result.get("error_code") or "")
        if error_code in CATALOG:
            failure["error_code"] = error_code
        return failure
    return result


def configuration_failure(reason: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": "Hardware configuration is unavailable",
        "reason": reason,
    }


def log_boundary_failure(
    logger: logging.Logger,
    message: str,
    exc: BaseException,
    *args: object,
    level: int = logging.ERROR,
) -> None:
    logger.log(level, f"{message} exception_type=%s", *args, type(exc).__name__)
