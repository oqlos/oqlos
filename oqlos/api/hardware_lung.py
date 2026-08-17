"""Artificial lung motor and logical lung command routes."""

from __future__ import annotations

from typing import Any, NoReturn

from fastapi import APIRouter, Body

from oqlos.api.hardware_gateway import get_hardware_gateway
from oqlos.errors import OqlosError
from oqlos.hardware.artificial_lung import execute_command as execute_artificial_lung_command
from oqlos.hardware.artificial_lung import get_peripheral_status as get_artificial_lung_status
from oqlos.hardware.tic249_units import TIC249_DEFAULT_TARGET_VELOCITY

router = APIRouter(tags=["hardware-lung"])
_LUNG_OPERATION_BY_STATUS = {
    "start": "artificial-lung.start",
    "stopped": "artificial-lung.stop",
    "de-energized": "artificial-lung.disable",
}


def command_payload(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    command = str(payload.get("command") or "").strip()
    if not command:
        raise OqlosError(
            code="api_diagnostic_command_invalid",
            status_code=422,
            detail={
                "architecture": "SOA",
                "layer": "firmware",
                "component": "artificial-lung",
                "stage": "command.validate",
                "problem_source": "request",
                "operation_id": "artificial-lung.command",
                "field": "command",
                "expected": "non-empty string",
            },
        )
    from oqlos.api.command_kwargs import validate_args_or_params_types

    try:
        args = validate_args_or_params_types(payload, prefer="args")
    except ValueError as exc:
        field = str(exc) or "args"
        raise OqlosError(
            code="api_diagnostic_command_invalid",
            status_code=422,
            detail={
                "architecture": "SOA",
                "layer": "firmware",
                "component": "artificial-lung",
                "stage": "command.validate",
                "problem_source": "request",
                "operation_id": "artificial-lung.command",
                "field": field,
                "expected": "object",
            },
        ) from None
    return command, args


def _raise_tic249_failure(
    status: str,
    *,
    reason: str = "tic249-command-failed",
    cause: Exception | None = None,
) -> NoReturn:
    error = OqlosError(
        code="hw_tic249_sidecar_unreachable",
        status_code=503,
        detail={
            "architecture": "SOA",
            "layer": "firmware",
            "component": "artificial-lung",
            "stage": "command.execute",
            "problem_source": "hardware",
            "operation_id": _LUNG_OPERATION_BY_STATUS.get(
                status, "artificial-lung.command"
            ),
            "upstream_target": "hardware-plugin://motor-tic249",
            "status": status,
            "reason": reason,
        },
    )
    if cause is not None:
        raise error from cause
    raise error


async def lung_state_response(action: Any, status: str) -> dict[str, Any]:
    ok = await action()
    if not ok:
        _raise_tic249_failure(status)
    return {"ok": True, "status": status}


@router.post("/lung")
async def set_lung(steps: int = 500, speed: int = TIC249_DEFAULT_TARGET_VELOCITY, cycles: int = 5, pause: float = 0.5):
    """Start artificial lung reciprocating motion (tic249 stepper)."""
    gateway = get_hardware_gateway()
    detailed_result: dict[str, Any] | None = None
    if hasattr(gateway, "set_lung_result"):
        try:
            maybe_result = await gateway.set_lung_result(steps=steps, speed=speed, cycles=cycles, pause=pause)
            if isinstance(maybe_result, dict):
                detailed_result = maybe_result
            else:
                _raise_tic249_failure("start", reason="invalid-adapter-response")
        except (OSError, RuntimeError) as exc:
            _raise_tic249_failure("start", cause=exc)

    if detailed_result is None:
        ok = await gateway.set_lung(steps=steps, speed=speed, cycles=cycles, pause=pause)
        if not ok:
            _raise_tic249_failure("start")
        return {"steps": steps, "speed": speed, "cycles": cycles, "pause": pause, "ok": True}

    payload: dict[str, Any] = {
        "steps": steps,
        "speed": speed,
        "cycles": cycles,
        "pause": pause,
        "ok": bool(detailed_result.get("success", False)),
    }
    if detailed_result.get("data") is not None:
        payload["data"] = detailed_result.get("data")
    if not payload["ok"]:
        _raise_tic249_failure("start")
    return payload


@router.post("/lung/stop", summary="Emergency stop the artificial lung motor")
async def stop_lung():
    return await lung_state_response(get_hardware_gateway().stop_lung, "stopped")


@router.post("/lung/disable", summary="De-energize the artificial lung motor")
async def disable_lung():
    return await lung_state_response(get_hardware_gateway().disable_lung, "de-energized")


@router.get("/artificial-lung/status")
async def artificial_lung_status():
    """Logical lung state merged with motor connectivity hints."""
    return await get_artificial_lung_status(get_hardware_gateway())


@router.post("/artificial-lung/command")
async def artificial_lung_command(payload: dict[str, Any] = Body(default_factory=dict)):
    """Execute artificial-lung logical commands (set_lpm, lung_*, emergency_stop)."""
    command, args = command_payload(payload)
    return await execute_artificial_lung_command(command, args, get_hardware_gateway())
