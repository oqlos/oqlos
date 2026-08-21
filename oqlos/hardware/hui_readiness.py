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
    """Control plugins probed for readiness, valve alternatives first."""
    return (*gateway_valve_controllers(gateway), *_HUI_MOTOR_PLUGINS)


def _hui_valve_plugin(gateway: Any) -> str:
    """Preferred valve output module (the first configured alternative)."""
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
    cached_readiness = getattr(gateway, "plugin_cached_readiness", None)
    if callable(cached_readiness):
        try:
            return _public_readiness(await cached_readiness(plugin_id), plugin_id)
        except Exception:
            pass
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


def _valve_action_state(
    controllers: tuple[str, ...],
    controls: dict[str, dict[str, Any]],
    *required: str,
) -> dict[str, Any]:
    active = next(
        (plugin_id for plugin_id in controllers if controls.get(plugin_id, {}).get("ok")),
        None,
    )
    unavailable_required = [
        plugin_id for plugin_id in required if not controls.get(plugin_id, {}).get("ok")
    ]
    return {
        "ready": active is not None and not unavailable_required,
        "required_hardware": [*(active and [active] or list(controllers)), *required],
        "valve_controller_alternatives": list(controllers),
        "active_valve_controller": active,
        "unavailable_hardware": [
            *([] if active else list(controllers)),
            *unavailable_required,
        ],
    }


async def build_hui_readiness(
    gateway: Any,
    *,
    analog_input_health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fast, non-reconnecting HUI preflight with control/telemetry separation."""
    valve_controllers = tuple(gateway_valve_controllers(gateway))
    if not valve_controllers:
        valve_controllers = (MODBUS_VALVE_CONTROLLER,)
    checks = await asyncio.gather(
        *(
            _read_plugin_without_reconnect(gateway, plugin_id)
            for plugin_id in _hui_control_plugins(gateway)
        )
    )
    controls = {check["plugin_id"]: check for check in checks}
    valve_plugin = next(
        (
            plugin_id
            for plugin_id in valve_controllers
            if controls.get(plugin_id, {}).get("ok")
        ),
        valve_controllers[0],
    )

    from oqlos.hardware.hui_hold import get_hui_hold_profiles

    hold_actions: dict[str, dict[str, Any]] = {}
    for key, profile in get_hui_hold_profiles().items():
        motors = (("motor-dri0050",) if float(profile["pump_pct"]) else ())
        hold_actions[key] = _valve_action_state(valve_controllers, controls, *motors)

    telemetry = _telemetry_readiness(analog_input_health)
    controls_ready = any(
        controls.get(plugin_id, {}).get("ok") for plugin_id in valve_controllers
    ) and all(controls.get(plugin_id, {}).get("ok") for plugin_id in _HUI_MOTOR_PLUGINS)
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
            "valves": _valve_action_state(valve_controllers, controls),
            "artificial_lung_start": _valve_action_state(
                valve_controllers, controls, "motor-tic249"
            ),
            "artificial_lung_stop": {
                **_action_state(("motor-tic249",), controls),
                "best_effort_hardware": [valve_plugin],
                "valve_controller_alternatives": list(valve_controllers),
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
        "valve_controllers": {
            "preference": list(valve_controllers),
            "active": valve_plugin if controls.get(valve_plugin, {}).get("ok") else None,
            "fallback": [
                plugin_id for plugin_id in valve_controllers if plugin_id != valve_plugin
            ],
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

    # Hardware health probes may each consume their transport timeout. Run the
    # independent checks together so a short Process URI does not turn two clear
    # device failures into an opaque gateway timeout.
    if not reconnect:
        checks = list(
            await asyncio.gather(
                *(_read_plugin_without_reconnect(gateway, plugin_id) for plugin_id in required)
            )
        )
    else:
        readiness = getattr(gateway, "plugin_readiness", None)
        if not callable(readiness):
            return None
        checks = list(
            await asyncio.gather(
                *(readiness(plugin_id, reconnect=True) for plugin_id in required)
            )
        )
    controllers = tuple(gateway_valve_controllers(gateway))
    valve_ids = tuple(plugin_id for plugin_id in required if plugin_id in controllers)
    strict_ids = tuple(plugin_id for plugin_id in required if plugin_id not in valve_ids)
    by_id = {str(check.get("plugin_id") or ""): check for check in checks}
    valve_ready = not valve_ids or any(by_id.get(plugin_id, {}).get("ok") for plugin_id in valve_ids)
    unavailable = [
        by_id[plugin_id]
        for plugin_id in strict_ids
        if not by_id.get(plugin_id, {}).get("ok")
    ]
    if valve_ids and not valve_ready:
        unavailable = [
            *[by_id.get(plugin_id, {"plugin_id": plugin_id, "ok": False}) for plugin_id in valve_ids],
            *unavailable,
        ]
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
