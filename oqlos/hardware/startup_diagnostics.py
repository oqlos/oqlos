"""Run hardware diagnosis (and optional safe auto-repair) at OqlOS startup.

Wired into the app lifespan after plugin initialization. The result is
cached in-process so the UI can show "what happened at boot" without
re-scanning. This must never raise — a diagnostics failure may not block
the hardware runtime from serving.

Env flags:
  OQLOS_STARTUP_DIAGNOSTICS   default "1" — run diagnosis on startup
  OQLOS_STARTUP_AUTO_REPAIR   default "1" — attempt safe recover when degraded
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

_last_result: dict[str, Any] | None = None


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def last_startup_diagnostics() -> dict[str, Any] | None:
    """Cached result of the most recent startup diagnostics run (or None)."""
    return _last_result


def _report_is_degraded(report: dict[str, Any]) -> bool:
    """Heuristic: a diagnosis report is degraded if any device is not ok."""
    if not isinstance(report, dict):
        return False
    if report.get("overall_ok") is False or report.get("degraded") is True:
        return True
    devices = report.get("devices")
    if isinstance(devices, list):
        for dev in devices:
            if isinstance(dev, dict) and dev.get("ok") is False:
                return True
    return False


async def run_startup_diagnostics_and_repair() -> dict[str, Any]:
    """Diagnose hardware at startup and optionally attempt a safe repair.

    Returns a summary dict; never raises. Also stored for later retrieval
    via :func:`last_startup_diagnostics`.
    """
    global _last_result

    if not _flag("OQLOS_STARTUP_DIAGNOSTICS", True):
        _last_result = {"ran": False, "reason": "disabled by OQLOS_STARTUP_DIAGNOSTICS"}
        return _last_result

    started = time.time()
    summary: dict[str, Any] = {"ran": True, "timestamp": started}

    try:
        from oqlos.api.hardware_gateway import get_hardware_gateway
        from oqlos.api.hardware_identify import hardware_identify
        from oqlos.hardware.diagnosis import (
            build_diagnosis_report,
            execute_safe_recover,
            report_to_dict,
        )

        identify_payload = await hardware_identify(scan="never")
        report = build_diagnosis_report(identify_payload)
        report_dict = report_to_dict(report)
        summary["diagnosis"] = report_dict
        degraded = _report_is_degraded(report_dict)
        summary["degraded"] = degraded

        if degraded and _flag("OQLOS_STARTUP_AUTO_REPAIR", True):
            logger.warning("Startup diagnostics: hardware degraded — attempting safe auto-repair")
            try:
                execution = await execute_safe_recover(get_hardware_gateway(), report)
                summary["repair"] = execution
                summary["repaired"] = bool(execution.get("ok", execution.get("success")))
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Startup auto-repair failed")
                summary["repair"] = {"ok": False, "error": str(exc)}
                summary["repaired"] = False
        elif degraded:
            summary["repair"] = {"ok": False, "skipped": "OQLOS_STARTUP_AUTO_REPAIR disabled"}
        else:
            logger.info("Startup diagnostics: hardware healthy")
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Startup diagnostics failed")
        summary["error"] = str(exc)

    summary["duration_sec"] = round(time.time() - started, 3)
    _last_result = summary
    return summary


__all__ = ["last_startup_diagnostics", "run_startup_diagnostics_and_repair"]
