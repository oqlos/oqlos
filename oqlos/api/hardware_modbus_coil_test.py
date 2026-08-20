"""Guarded, one-coil-at-a-time BoardNet wiring test."""

from __future__ import annotations

import asyncio
from typing import Any

from oqlos.api.hardware_gateway import get_hardware_gateway, try_get_hardware_gateway
from oqlos.config import get_settings
from oqlos.errors import OqlosError
from oqlos.hardware.modbus_io_catalog import MODBUS_IO_COIL_COUNT, build_coil_catalog
from oqlos.hardware.power_safety import ensure_power_safe
from oqlos.hardware.valve_controller import M5_VALVE_CONTROLLER, gateway_valve_controllers

_settings = get_settings()
_coil_test_lock = asyncio.Lock()
MIN_PULSE_MS = 100
MAX_PULSE_MS = 1000


def _controller_issue_code(plugin_id: str | None) -> str:
    return "hw_m5_4in8out_no_response" if plugin_id == M5_VALVE_CONTROLLER else "hw_modbus_no_response"


async def _controller() -> tuple[str, Any, Any]:
    gateway = get_hardware_gateway()
    controllers = gateway_valve_controllers(gateway)
    checks: list[dict[str, Any]] = []
    for reconnect in (False, True):
        for plugin_id in controllers:
            check = await gateway.plugin_readiness(plugin_id, reconnect=reconnect)
            checks.append(check)
            if not check.get("ok"):
                continue
            plugin = await gateway._get_or_connect_plugin(plugin_id)
            if plugin is not None:
                return plugin_id, plugin, gateway
        if any(check.get("ok") for check in checks):
            break
    raise OqlosError(
        code=_controller_issue_code(controllers[0] if controllers else None),
        status_code=503,
        message="No configured valve controller is available",
        detail={"controllers": controllers, "readiness": checks},
    )


def _coil_catalog(states: list[bool]) -> list[dict[str, Any]]:
    rows = build_coil_catalog(states[:MODBUS_IO_COIL_COUNT])
    rows.extend(
        {
            "sequence": address + 1,
            "id": f"DO{address + 1}",
            "address": address,
            "address_hex": f"output:{address}",
            "primary_valve_id": f"valve-{address + 1}",
            "aliases": [f"m5_out_{address + 1}"],
            "uses": [],
            "state": states[address],
        }
        for address in range(MODBUS_IO_COIL_COUNT, len(states))
    )
    return rows


async def build_coil_test_plan() -> dict[str, Any]:
    issue_code: str | None = None
    issue_message: str | None = None
    controllers: list[str] = []
    try:
        plugin_id, plugin, gateway = await _controller()
        controllers = gateway_valve_controllers(gateway)
        result = await plugin.execute_command("read_io_snapshot", {})
        if not result.get("success"):
            raise OqlosError(
                code=_controller_issue_code(plugin_id),
                status_code=503,
                message=str(result.get("error") or f"{plugin_id} snapshot failed"),
            )
        data = result.get("data") or {}
        states = [bool(value) for value in (data.get("outputs") or data.get("coils") or [])]
        inputs = [bool(value) for value in (data.get("inputs") or data.get("discrete_inputs") or [])]
        config = gateway._plugin_configs.get(plugin_id)
        params = config.connection_params if config is not None else {}
        module = {
            "module_role": plugin_id,
            "ok": True,
            "device_id": params.get("device_id"),
            "endpoint": params.get("base_url") or params.get("serial_port"),
            "transport": getattr(config, "connection_type", None),
            "message": "Active valve controller",
            "config_registers": [],
            "states": states,
            "inputs": inputs,
        }
    except OqlosError as exc:
        # A disconnected module must keep the test fail-closed, but the plan is
        # still a read-only UI projection. Return the configured identity and
        # DO1-DO8 catalogue instead of replacing the whole view with a 503.
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        configured = detail.get("controllers")
        if isinstance(configured, list):
            controllers = [str(item) for item in configured if str(item).strip()]
        readiness = detail.get("readiness")
        readiness = readiness if isinstance(readiness, list) else []
        primary_check = next(
            (item for item in readiness if isinstance(item, dict)),
            {},
        )
        module = {
            "module_role": controllers[0] if controllers else "valve-controller",
            "ok": False,
            "device_id": primary_check.get("device_id"),
            "endpoint": primary_check.get("endpoint"),
            "transport": primary_check.get("transport"),
            "message": str(primary_check.get("message") or exc.message),
            "config_registers": [],
            "states": [],
            "inputs": [],
        }
        issue_code = exc.public_code
        issue_message = exc.message
    states = list(module.get("states") or [])
    reasons: list[str] = []
    if issue_message:
        reasons.append(issue_message)
    if not module.get("ok"):
        module_message = str(module.get("message") or "valve controller is unavailable")
        if module_message not in reasons:
            reasons.append(module_message)
    if module.get("ok") and len(states) < MODBUS_IO_COIL_COUNT:
        reasons.append(f"Expected at least 8 output states, received {len(states)}")
    energized = [f"DO{index + 1}" for index, value in enumerate(states) if value]
    if energized:
        reasons.append(f"Outputs already energized: {', '.join(energized)}")

    ready = not reasons
    return {
        "ok": bool(module.get("ok")),
        "ready": ready,
        "mode": str(getattr(_settings, "hardware_mode", "unknown")),
        "error_code": issue_code,
        "safety": {
            "one_coil_at_a_time": True,
            "automatic_off": True,
            "max_pulse_ms": MAX_PULSE_MS,
            "requires_confirmation": True,
            "blocked_reasons": reasons,
        },
        "module": {
            "role": module.get("module_role", "modbus-io"),
            "active_controller": module.get("module_role"),
            "controller_preference": controllers,
            "fallback_controllers": [
                item for item in controllers if item != module.get("module_role")
            ],
            "device_id": module.get("device_id"),
            "serial_port": module.get("endpoint"),
            "endpoint": module.get("endpoint"),
            "transport": module.get("transport"),
            "output_count": len(states),
            "input_count": len(module.get("inputs") or []),
            "inputs": list(module.get("inputs") or []),
            "message": module.get("message"),
            "config_registers": module.get("config_registers") or [],
        },
        "coils": _coil_catalog(states),
    }


async def _plugin() -> Any:
    _plugin_id, plugin, _gateway = await _controller()
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
    if not 0 <= address < 16:
        raise OqlosError(
            code="api_modbus_wizard_invalid_request",
            status_code=422,
            message="address must be between 0 and 15",
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
        await ensure_power_safe(gateway, operation="valve-controller.coil-test.pulse")
    async with _coil_test_lock:
        plan = await build_coil_test_plan()
        if not plan.get("ready"):
            reasons = plan.get("safety", {}).get("blocked_reasons") or []
            raise OqlosError(
                code=_controller_issue_code(plan.get("module", {}).get("active_controller")),
                status_code=503,
                message="coil test preflight failed",
                detail={"blocked_reasons": reasons, "plan": plan},
            )
        if address >= len(plan.get("coils") or []):
            raise OqlosError(
                code="api_modbus_wizard_invalid_request",
                status_code=422,
                message=f"DO{address + 1} is not exposed by the active controller",
                detail={"payload": payload, "plan": plan},
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
                code=_controller_issue_code(plan.get("module", {}).get("active_controller")),
                status_code=503,
                message=str(error or "coil test did not leave outputs safe"),
                detail=payload,
            )
        return payload


def _off_operations(result: dict[str, Any], count: int) -> list[dict[str, Any]]:
    return [
        {
            "coil": f"DO{address + 1}",
            "ok": True,
            "result": {**dict(result), "coil": address, "value": False},
        }
        for address in range(count)
    ]


async def stop_all_coils() -> dict[str, Any]:
    """Best-effort emergency de-energize; safe even when preflight cannot read."""
    # Waiting on the same lock lets an in-flight pulse finish its mandatory OFF
    # without introducing a second RTU writer or a release/reacquire race.
    async with _coil_test_lock:
        plan = await build_coil_test_plan()
        count = max(MODBUS_IO_COIL_COUNT, len(plan.get("coils") or []))
        try:
            plugin = await _plugin()
        except OqlosError:
            raise
        except Exception as exc:
            raise OqlosError(
                code=_controller_issue_code(plan.get("module", {}).get("active_controller")),
                status_code=503,
                message=str(exc),
                detail={"operations": []},
            ) from exc
        # Waveshare IO 8CH has a single safe-off coil (0x00FF). Eight sequential
        # RTU writes lose to a busy bus even when diagnosis/health still reads OK.
        broadcast = await plugin.execute_command("all_outputs_off", {})
        if broadcast.get("success"):
            return {
                "ok": True,
                "method": "all_outputs_off",
                "controller": plan.get("module", {}).get("active_controller"),
                "operations": _off_operations(
                    broadcast.get("data") or {"all_outputs": True}, count
                ),
            }

        operations: list[dict[str, Any]] = []
        for address in range(count):
            try:
                result = await _write_coil(plugin, address, False)
                operations.append({"coil": f"DO{address + 1}", "ok": True, "result": result})
            except Exception as exc:
                operations.append({"coil": f"DO{address + 1}", "ok": False, "error": str(exc)})
        if not all(operation["ok"] for operation in operations):
            failed = [row["coil"] for row in operations if not row["ok"]]
            raise OqlosError(
                code=_controller_issue_code(plan.get("module", {}).get("active_controller")),
                status_code=503,
                message=(
                    "Failed to de-energize "
                    + ", ".join(failed)
                    + f" (all_outputs_off: {broadcast.get('error') or 'failed'})"
                ),
                detail={
                    "method": "per_coil_fallback",
                    "broadcast_error": broadcast.get("error") or "all_outputs_off failed",
                    "operations": operations,
                },
            )
        return {
            "ok": True,
            "method": "per_coil_fallback",
            "operations": operations,
        }
