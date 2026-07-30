"""Typed, sanitizing error boundary for the isolated Modbus wizard."""

from __future__ import annotations

import re
from typing import Any, Callable, NoReturn

from oqlos.errors import OqlosError

_SAFE_SERIAL_LABEL = re.compile(r"[A-Za-z0-9._:-]{1,64}")


def _wizard_config_is_readable(config: dict[str, Any]) -> bool:
    """Reject empty or partial replies masquerading as device config."""
    try:
        device_id = int(config.get("device_id"))
        baudrate = int(config.get("baudrate"))
    except (TypeError, ValueError):
        return False
    parity = str(config.get("parity") or "").upper()
    return 1 <= device_id <= 255 and baudrate > 0 and parity in {"N", "E", "O"}


def _modbus_wizard_serial_target(serial_port: str) -> str:
    """Return a bounded serial target without reflecting arbitrary input."""
    label = str(serial_port or "").rsplit("/", 1)[-1]
    if not _SAFE_SERIAL_LABEL.fullmatch(label):
        label = "configured-adapter"
    return f"serial-device://{label}"


def _modbus_wizard_issue_for_exception(exc: Exception) -> str:
    """Classify adapter failures without publishing their message."""
    normalized = str(exc).lower()
    if any(
        marker in normalized
        for marker in (
            "port is busy",
            "resource busy",
            "could not exclusively lock",
            "already open",
        )
    ):
        return "serial_port_busy"
    if any(
        marker in normalized
        for marker in ("no response", "did not respond", "timed out", "timeout")
    ):
        return "hw_modbus_no_response"
    return "modbus_preflight_exception"


def _raise_modbus_wizard_failure(
    *,
    issue_code: str,
    stage: str,
    operation_id: str,
    serial_port: str,
    cause: Exception | None = None,
) -> NoReturn:
    status_code = 409 if issue_code == "serial_port_busy" else 503
    error = OqlosError(
        code=issue_code,
        status_code=status_code,
        detail={
            "architecture": "SOA",
            "layer": "firmware",
            "component": "modbus-wizard",
            "stage": stage,
            "problem_source": "hardware",
            "operation_id": operation_id,
            "upstream_target": _modbus_wizard_serial_target(serial_port),
        },
    )
    if cause is not None:
        raise error from cause
    raise error


def _raise_pimodbus_unavailable(*, operation_id: str, cause: Exception) -> NoReturn:
    raise OqlosError(
        code="pimodbus_unavailable",
        status_code=503,
        detail={
            "architecture": "SOA",
            "layer": "firmware",
            "component": "modbus-wizard",
            "stage": "dependency.load",
            "problem_source": "dependency",
            "operation_id": operation_id,
            "upstream_target": "python-package://pimodbus",
        },
    ) from cause


def _modbus_wizard_probe_checked(
    probe: Callable[..., dict[str, Any]],
    serial_port: str,
    baudrates: list[int],
    parities: list[str],
    device_ids: list[int],
    required_roles: list[str] | None = None,
) -> dict[str, Any]:
    """Run the probe and convert negative/exceptional outcomes to typed errors."""
    try:
        result = probe(
            serial_port,
            baudrates,
            parities,
            device_ids,
            required_roles,
        )
    except OqlosError:
        raise
    except Exception as exc:
        _raise_modbus_wizard_failure(
            issue_code=_modbus_wizard_issue_for_exception(exc),
            stage="probe.execute",
            operation_id="modbus.wizard.probe-isolated",
            serial_port=serial_port,
            cause=exc,
        )
    if not bool(result.get("ok")):
        _raise_modbus_wizard_failure(
            issue_code="hw_modbus_no_response",
            stage="probe.scan",
            operation_id="modbus.wizard.probe-isolated",
            serial_port=serial_port,
        )
    return result
