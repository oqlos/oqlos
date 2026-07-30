"""Sanitizing result and exception boundaries for Waveshare diagnostics."""

from __future__ import annotations

from typing import Any, Callable, NoReturn

from oqlos.api.hardware_modbus_wizard_boundary import (
    _modbus_wizard_issue_for_exception,
    _modbus_wizard_serial_target,
)
from oqlos.errors import OqlosError
from oqlos.errors.c2004_catalog_generated import c2004_code_for_issue

_OPERATION_ID = "modbus.waveshare.diagnose"


def _waveshare_diagnostic_failure(
    *,
    issue_code: str,
    status: str,
    reason: str,
    device_id: int | None = None,
) -> dict[str, Any]:
    """Build a stable negative diagnostic result without exception text."""
    public_code = c2004_code_for_issue(issue_code)
    result: dict[str, Any] = {
        "ok": False,
        "status": status,
        "reason": reason,
        "error": reason,
        "code": public_code,
        "error_code": public_code,
        "diagnostics": {"issue_code": issue_code, "code": public_code},
    }
    if device_id is not None:
        result["device_id"] = device_id
    return result


def _waveshare_transport_failure(
    *, cause: Exception, status: str, reason: str
) -> dict[str, Any]:
    """Classify a transport exception without exposing its message."""
    return _waveshare_diagnostic_failure(
        issue_code=_modbus_wizard_issue_for_exception(cause),
        status=status,
        reason=reason,
    )


def _read_output_control_modes(
    serial_port: str,
    baudrate: int,
    parity: str,
    device_id: int,
    timeout: float = 1.5,
) -> dict[str, Any]:
    """Read Waveshare control registers behind a sanitizing transport boundary."""
    try:
        from pymodbus.client import ModbusSerialClient  # type: ignore
        from pymodbus.exceptions import ModbusException
    except ImportError:
        return _waveshare_diagnostic_failure(
            issue_code="pimodbus_unavailable",
            status="dependency-unavailable",
            reason="pymodbus-unavailable",
        )

    client = None
    try:
        client = ModbusSerialClient(
            port=serial_port,
            baudrate=int(baudrate),
            parity=str(parity),
            stopbits=1,
            bytesize=8,
            timeout=float(timeout),
        )
        if not client.connect():
            return _waveshare_diagnostic_failure(
                issue_code="hw_modbus_no_response",
                status="no-response",
                reason="serial-connection-unavailable",
            )
        result = client.read_holding_registers(
            address=0x1000, count=8, device_id=int(device_id)
        )
        if not result or result.isError():
            return _waveshare_diagnostic_failure(
                issue_code="hw_modbus_no_response",
                status="no-response",
                reason="control-register-read-failed",
            )
        registers = list(getattr(result, "registers", []) or [])
        return {"ok": True, "registers": registers}
    except (OSError, RuntimeError, ValueError, ModbusException) as exc:
        return _waveshare_transport_failure(
            cause=exc,
            status="read-error",
            reason="control-register-read-failed",
        )
    finally:
        if client is not None:
            try:
                client.close()
            except (OSError, RuntimeError, ModbusException):
                pass


def _waveshare_probe_checked(
    probe: Callable[..., tuple[dict[str, Any], bool]],
    *args: Any,
    serial_port: str,
) -> tuple[dict[str, Any], bool]:
    """Execute one topology probe and type expected transport failures."""
    from pymodbus.exceptions import ModbusException

    try:
        return probe(*args)
    except (OSError, RuntimeError, ModbusException) as exc:
        _raise_waveshare_probe_failure(serial_port=serial_port, cause=exc)


def _waveshare_report_outcome(
    report_ok: bool, per_slave: dict[str, Any]
) -> tuple[bool, str]:
    """Summarize a scan and its detailed reads as an observation status."""
    if not report_ok:
        return False, "unavailable"
    if all(bool(item.get("ok")) for item in per_slave.values()):
        return True, "healthy"
    return False, "degraded"


def _raise_waveshare_probe_failure(*, serial_port: str, cause: Exception) -> NoReturn:
    """Map an expected adapter failure to safe RFC 9457 context."""
    issue_code = _modbus_wizard_issue_for_exception(cause)
    raise OqlosError(
        code=issue_code,
        status_code=409 if issue_code == "serial_port_busy" else 503,
        detail={
            "architecture": "SOA",
            "layer": "firmware",
            "component": "modbus-waveshare",
            "stage": "matrix.scan",
            "problem_source": "hardware",
            "operation_id": _OPERATION_ID,
            "upstream_target": _modbus_wizard_serial_target(serial_port),
        },
    ) from cause


def _raise_waveshare_dependency_unavailable(*, cause: ImportError) -> NoReturn:
    """Raise a typed dependency error without reflecting the import message."""
    raise OqlosError(
        code="pimodbus_unavailable",
        status_code=503,
        detail={
            "architecture": "SOA",
            "layer": "firmware",
            "component": "modbus-waveshare",
            "stage": "dependency.load",
            "problem_source": "dependency",
            "operation_id": _OPERATION_ID,
            "upstream_target": "python-package://pimodbus",
        },
    ) from cause
