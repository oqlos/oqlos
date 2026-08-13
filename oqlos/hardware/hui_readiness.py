"""Shared fail-fast readiness checks for HUI hardware actions."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from oqlos.hardware.power_safety import power_actuation_failure
from oqlos.hardware.valve_controller import (
    MODBUS_VALVE_CONTROLLER,
    gateway_valve_controllers,
)

_HUI_MOTOR_PLUGINS = ("motor-dri0050", "motor-tic249")


def _hui_control_plugins(gateway: Any) -> tuple[str, ...]:
    """Control plugins probed for readiness, valve controller first."""
    return (_hui_valve_plugin(gateway), *_HUI_MOTOR_PLUGINS)


def _hui_valve_plugin(gateway: Any) -> str:
    """Valve output module this stand actually uses (modbus-io or M5 4In8Out)."""
    controllers = gateway_valve_controllers(gateway)
    return controllers[0] if controllers else MODBUS_VALVE_CONTROLLER


def _public_readiness(check: Any, plugin_id: str) -> dict[str, Any]:
    if not isinstance(check, dict):
        return {
            "ok": False,
            "plugin_id": plugin_id,
            "status": "unknown",
            "message": "Plugin readiness returned an invalid response",
        }
    return {
        "ok": bool(check.get("ok")),
        "plugin_id": plugin_id,
        "status": str(check.get("status") or ("ok" if check.get("ok") else "unknown")),
        "message": str(check.get("message") or "")[:256],
    }


async def _read_plugin_without_reconnect(gateway: Any, plugin_id: str) -> dict[str, Any]:
    readiness = getattr(gateway, "plugin_readiness", None)
    if not callable(readiness):
        return _public_readiness(None, plugin_id)
    try:
        return _public_readiness(
            await readiness(plugin_id, reconnect=False),
            plugin_id,
        )
    except TypeError:
        # Compatibility with small test/local gateways predating reconnect=.
        try:
            return _public_readiness(await readiness(plugin_id), plugin_id)
        except Exception:
            pass
    except Exception:
        pass
    return {
        "ok": False,
        "plugin_id": plugin_id,
        "status": "error",
        "message": "Plugin readiness check failed",
    }


def _telemetry_readiness(analog_input_health: dict[str, Any] | None) -> dict[str, Any]:
    if analog_input_health is None:
        return {
            "ready": None,
            "status": "not_configured",
            "components": {},
            "impact": "HUI control is unaffected; SC/WC telemetry availability is unknown",
        }
    raw_components = analog_input_health.get("components")
    raw_components = raw_components if isinstance(raw_components, dict) else {}
    components: dict[str, dict[str, Any]] = {}
    for device_id in ("usb-adc-mcp2221", "usb-adc-dfr1184"):
        raw = raw_components.get(device_id)
        item = raw if isinstance(raw, dict) else {}
        components[device_id] = {
            "ok": bool(item.get("ok")),
            "status": str(item.get("status") or ("ok" if item.get("ok") else "unavailable")),
            "message": str(item.get("message") or "No component health data")[:256],
            **({"transport": str(item["transport"])} if item.get("transport") else {}),
            **({"endpoint": str(item["endpoint"])} if item.get("endpoint") else {}),
        }
    ready = bool(analog_input_health.get("ok")) and all(
        component["ok"] for component in components.values()
    )
    return {
        "ready": ready,
        "status": "ready" if ready else "degraded",
        "components": components,
        "impact": (
            "SC/WC telemetry available"
            if ready
            else "HUI control remains available where control plugins are ready; SC/WC values may be empty"
        ),
    }


def _action_state(required: tuple[str, ...], controls: dict[str, dict[str, Any]]) -> dict[str, Any]:
    unavailable = [plugin_id for plugin_id in required if not controls[plugin_id]["ok"]]
    return {
        "ready": not unavailable,
        "required_hardware": list(required),
        "unavailable_hardware": unavailable,
    }


async def build_hui_readiness(
    gateway: Any,
    *,
    analog_input_health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fast, non-reconnecting HUI preflight with control/telemetry separation."""
    valve_plugin = _hui_valve_plugin(gateway)
    checks = await asyncio.gather(
        *(
            _read_plugin_without_reconnect(gateway, plugin_id)
            for plugin_id in _hui_control_plugins(gateway)
        )
    )
    controls = {check["plugin_id"]: check for check in checks}

    from oqlos.hardware.hui_hold import get_hui_hold_profiles

    hold_actions: dict[str, dict[str, Any]] = {}
    for key, profile in get_hui_hold_profiles().items():
        required = (valve_plugin,) + (("motor-dri0050",) if float(profile["pump_pct"]) else ())
        hold_actions[key] = _action_state(required, controls)

    telemetry = _telemetry_readiness(analog_input_health)
    controls_ready = all(check["ok"] for check in controls.values())
    telemetry_ready = telemetry["ready"] is not False
    status = "ready" if controls_ready and telemetry_ready else "degraded"
    return {
        "ok": status == "ready",
        "status": status,
        "controls_ready": controls_ready,
        "telemetry_ready": telemetry["ready"],
        "controls": controls,
        "telemetry": telemetry,
        "actions": {
            "holds": hold_actions,
            "valves": _action_state((valve_plugin,), controls),
            "artificial_lung_start": _action_state((valve_plugin, "motor-tic249"), controls),
            "artificial_lung_stop": {
                **_action_state(("motor-tic249",), controls),
                "best_effort_hardware": [valve_plugin],
            },
            "shutdown": {
                "ready": True,
                "full_confirmation": controls[valve_plugin]["ok"]
                and controls["motor-dri0050"]["ok"],
                "best_effort": True,
                "required_for_full_confirmation": ["motor-dri0050", valve_plugin],
            },
        },
        "diagnostic_endpoints": {
            "full": "/api/v1/hardware/diagnosis?scan=never",
            "valve_controller": f"/api/v1/plugins/{valve_plugin}/health",
            "modbus_io": "/api/v1/plugins/modbus-io/health",
            "analog_inputs": "/api/v1/hardware/sensors/batch",
        },
    }


async def required_plugins_failure(
    gateway: Any,
    plugin_ids: Iterable[str],
    *,
    command: str,
    key: str | None = None,
    check_power: bool = True,
    reconnect: bool = False,
) -> dict[str, Any] | None:
    """Return a structured failure before an HUI action touches hardware.

    Default ``reconnect=False``: use the already-initialized plugin map so a
    known-dead modbus-io does not burn the DisplayNet process timeout (5–15 s)
    on a serial re-open and surface as a false gateway 504 / C2004-HW-0011.
    Pass ``reconnect=True`` only for explicit recovery paths.
    """
    required = tuple(dict.fromkeys(str(plugin_id).strip() for plugin_id in plugin_ids if plugin_id))
    if not required or not getattr(gateway, "is_real", False):
        return None

    if check_power:
        payload = await power_actuation_failure(gateway, operation=command)
        if payload is not None:
            payload.update(
                {
                    "command": command,
                    "required_hardware": list(required),
                    "operations": [],
                }
            )
            if key is not None:
                payload["key"] = key
            return payload

    readiness = getattr(gateway, "plugin_readiness", None)
    if not callable(readiness):
        return None

    # Hardware health probes may each consume their transport timeout. Run the
    # independent checks together so a short Process URI does not turn two clear
    # device failures into an opaque gateway timeout.
    checks = list(
        await asyncio.gather(
            *(readiness(plugin_id, reconnect=reconnect) for plugin_id in required)
        )
    )
    unavailable = [check for check in checks if not check.get("ok")]
    if not unavailable:
        return None

    names = ", ".join(str(check.get("plugin_id") or "unknown") for check in unavailable)
    payload = {
        "ok": False,
        "command": command,
        "error": f"Required hardware unavailable: {names}",
        "error_code": "C2004-HW-0012",
        "status_code": 503,
        "required_hardware": list(required),
        "unavailable_hardware": unavailable,
        "operations": [],
        "safe_to_retry": False,
    }
    if key is not None:
        payload["key"] = key
    return payload
