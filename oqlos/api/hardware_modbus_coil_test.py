"""Guarded, one-coil-at-a-time BoardNet wiring test."""

from __future__ import annotations

import asyncio
from typing import Any

from oqlos.api.hardware_gateway import get_hardware_gateway, try_get_hardware_gateway
from oqlos.api.hardware_modbus_channels import read_modbus_profile_channels
from oqlos.config import get_settings
from oqlos.errors import OqlosError
from oqlos.hardware.modbus_io_catalog import MODBUS_IO_COIL_COUNT, build_coil_catalog
from oqlos.hardware.power_safety import ensure_power_safe

_settings = get_settings()
_coil_test_lock = asyncio.Lock()
MIN_PULSE_MS = 100
MAX_PULSE_MS = 1000


def _digital_output_states(module: dict[str, Any]) -> list[bool]:
    rows = [
        row for row in module.get("channels") or [] if row.get("kind") == "digital_output"
    ]
    rows.sort(key=lambda row: int(row.get("address", 0)))
    return [bool(row.get("value")) for row in rows[:MODBUS_IO_COIL_COUNT]]


async def build_coil_test_plan() -> dict[str, Any]:
    snapshot = await read_modbus_profile_channels("modbus-io")
    module = (snapshot.get("modules") or [{}])[0]
    states = _digital_output_states(module)
    reasons: list[str] = []
    if not module.get("ok"):
        reasons.append(str(module.get("message") or "modbus-io is unavailable"))
    if module.get("ok") and len(states) != MODBUS_IO_COIL_COUNT:
        reasons.append(
            f"Expected {MODBUS_IO_COIL_COUNT} coil states, received {len(states)}"
        )
    energized = [f"DO{index + 1}" for index, value in enumerate(states) if value]
    if energized:
        reasons.append(f"Outputs already energized: {', '.join(energized)}")

    ready = not reasons
    return {
        "ok": bool(module.get("ok")),
        "ready": ready,
        "mode": str(getattr(_settings, "hardware_mode", "unknown")),
        "safety": {
            "one_coil_at_a_time": True,
            "automatic_off": True,
            "max_pulse_ms": MAX_PULSE_MS,
            "requires_confirmation": True,
            "blocked_reasons": reasons,
        },
        "module": {
            "role": module.get("module_role", "modbus-io"),
            "device_id": module.get("device_id"),
            "serial_port": module.get("serial_port"),
            "message": module.get("message"),
            "config_registers": module.get("config_registers") or [],
        },
        "coils": build_coil_catalog(states),
    }


async def _plugin() -> Any:
    plugin = await get_hardware_gateway()._get_or_connect_plugin("modbus-io")
    if plugin is None:
        raise OqlosError(
            code="hw_modbus_no_response",
            status_code=503,
            message="modbus-io plugin unavailable",
        )
    return plugin


async def _write_coil(plugin: Any, address: int, value: bool) -> dict[str, Any]:
    result = await plugin.execute_command("set_coil", {"coil": address, "value": value})
    if not result.get("success"):
        raise OqlosError(
            code="hw_modbus_no_response",
            status_code=503,
            message=str(result.get("error") or f"DO{address + 1} write failed"),
            detail={"coil": address, "value": value, "result": result},
        )
    return result.get("data") or {"coil": address, "value": value}


async def pulse_coil(payload: dict[str, Any]) -> dict[str, Any]:
    address = int(payload.get("address", -1))
    if not 0 <= address < MODBUS_IO_COIL_COUNT:
        raise OqlosError(
            code="api_modbus_wizard_invalid_request",
            status_code=422,
            message="address must be between 0 and 7",
            detail={"payload": payload},
        )
    duration_ms = int(payload.get("duration_ms", 300))
    if not MIN_PULSE_MS <= duration_ms <= MAX_PULSE_MS:
        raise OqlosError(
            code="api_modbus_wizard_invalid_request",
            status_code=422,
            message=f"duration_ms must be between {MIN_PULSE_MS} and {MAX_PULSE_MS}",
            detail={"payload": payload},
        )
    expected_confirmation = f"PULSE_DO{address + 1}"
    if str(payload.get("confirm") or "") != expected_confirmation:
        raise OqlosError(
            code="api_modbus_wizard_invalid_request",
            status_code=422,
            message=f"confirm must equal {expected_confirmation}",
            detail={"payload": payload, "expected_confirmation": expected_confirmation},
        )

    if _coil_test_lock.locked():
        raise OqlosError(
            code="api_modbus_wizard_invalid_request",
            status_code=422,
            message="another coil test is already running",
            detail={"payload": payload},
        )

    gateway = try_get_hardware_gateway()
    if gateway is not None:
        await ensure_power_safe(gateway, operation="modbus-io.coil-test.pulse")
    async with _coil_test_lock:
        plan = await build_coil_test_plan()
        if not plan.get("ready"):
            reasons = plan.get("safety", {}).get("blocked_reasons") or []
            raise OqlosError(
                code="hw_modbus_no_response",
                status_code=503,
                message="coil test preflight failed",
                detail={"blocked_reasons": reasons, "plan": plan},
            )

        plugin = await _plugin()
        on_result: dict[str, Any] | None = None
        off_result: dict[str, Any] | None = None
        error: str | None = None
        try:
            on_result = await _write_coil(plugin, address, True)
            await asyncio.sleep(duration_ms / 1000)
        except Exception as exc:  # OFF must still be attempted.
            error = str(exc)
        finally:
            try:
                off_result = await _write_coil(plugin, address, False)
            except Exception as exc:
                error = f"{error}; OFF failed: {exc}" if error else f"OFF failed: {exc}"

        after = await build_coil_test_plan()
        payload = {
            "ok": error is None and bool(after.get("ready")),
            "coil": f"DO{address + 1}",
            "address": address,
            "duration_ms": duration_ms,
            "on": on_result,
            "off": off_result,
            "error": error,
            "after": after,
        }
        if not payload["ok"]:
            raise OqlosError(
                code="hw_modbus_no_response",
                status_code=503,
                message=str(error or "coil test did not leave outputs safe"),
                detail=payload,
            )
        return payload


async def stop_all_coils() -> dict[str, Any]:
    """Best-effort emergency de-energize; safe even when preflight cannot read."""
    # Waiting on the same lock lets an in-flight pulse finish its mandatory OFF
    # without introducing a second RTU writer or a release/reacquire race.
    async with _coil_test_lock:
        try:
            plugin = await _plugin()
        except OqlosError:
            raise
        except Exception as exc:
            raise OqlosError(
                code="hw_modbus_no_response",
                status_code=503,
                message=str(exc),
                detail={"operations": []},
            ) from exc
        operations: list[dict[str, Any]] = []
        for address in range(MODBUS_IO_COIL_COUNT):
            try:
                result = await _write_coil(plugin, address, False)
                operations.append({"coil": f"DO{address + 1}", "ok": True, "result": result})
            except Exception as exc:
                operations.append({"coil": f"DO{address + 1}", "ok": False, "error": str(exc)})
        if not all(operation["ok"] for operation in operations):
            raise OqlosError(
                code="hw_modbus_no_response",
                status_code=503,
                message="Failed to de-energize one or more coils",
                detail={"operations": operations},
            )
        return {
            "ok": True,
            "operations": operations,
        }
