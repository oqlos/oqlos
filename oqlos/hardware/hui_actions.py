"""HUI domain actions for OqlOS-owned hardware recipes (facade)."""

from __future__ import annotations

from typing import Any

from oqlos.hardware.hui_artificial_lung import start_hui_artificial_lung, stop_hui_artificial_lung
from oqlos.hardware.hui_hold import (
    HUI_ALL_VALVE_IDS,
    HUI_HOLD_PROFILES,
    get_hui_hold_profiles,
    shutdown_all_hui_hardware,
    start_hui_hold,
    stop_hui_hold,
)
from oqlos.hardware.hui_readiness import build_hui_readiness
from oqlos.hardware.valve_controller import resolve_valve_controller_from_config
from oqlos.hardware.hui_valve import get_hui_valve_specs, run_hui_valve_key
from oqlos.hardware.hui_lung_recipe import (
    HUI_AL_LUNG_VALVE_ID,
    HUI_LUNG_MAX_SPEED_STEPS_PER_S,
    HUI_LUNG_PAUSE_SECONDS,
    HUI_LUNG_RAMP_SECONDS,
    HUI_LUNG_RECIPROCATE_ARGS,
    HUI_LUNG_STROKE_STEPS,
    get_hui_lung_reciprocate_args,
    get_hui_lung_valve_id,
)

__all__ = [
    "HUI_AL_LUNG_VALVE_ID",
    "HUI_ALL_VALVE_IDS",
    "HUI_HOLD_PROFILES",
    "HUI_LUNG_MAX_SPEED_STEPS_PER_S",
    "HUI_LUNG_PAUSE_SECONDS",
    "HUI_LUNG_RAMP_SECONDS",
    "HUI_LUNG_RECIPROCATE_ARGS",
    "HUI_LUNG_STROKE_STEPS",
    "get_hui_hold_profiles",
    "get_hui_lung_reciprocate_args",
    "get_hui_lung_valve_id",
    "get_hui_valve_specs",
    "build_hui_readiness",
    "list_hui_actions",
    "run_hui_valve_key",
    "shutdown_all_hui_hardware",
    "start_hui_artificial_lung",
    "start_hui_hold",
    "stop_hui_artificial_lung",
    "stop_hui_hold",
]


def list_hui_actions() -> dict[str, Any]:
    profiles = get_hui_hold_profiles()
    valve_specs = get_hui_valve_specs()
    # Valves run on whichever output module the configuration selects
    # (Waveshare modbus-io or the M5Stack 4In8Out I2C module).
    valve_plugin = resolve_valve_controller_from_config()
    return {
        "ok": True,
        "hold_keys": list(profiles.keys()),
        "valve_keys": list(valve_specs.keys()),
        "al_keys": ["al-start", "al-stop"],
        "profiles": {
            key: {
                "valves_on": list(profile["valves_on"]),
                "pump_pct": profile["pump_pct"],
                "required_hardware": [
                    valve_plugin,
                    *(["motor-dri0050"] if float(profile["pump_pct"]) else []),
                ],
            }
            for key, profile in profiles.items()
        },
        "valve_specs": {
            key: {"valve_id": spec["valve_id"], "value": bool(spec["value"])}
            for key, spec in valve_specs.items()
        },
        "artificial_lung": {
            "valve_id": get_hui_lung_valve_id(),
            "reciprocate_args": get_hui_lung_reciprocate_args(),
            "start_required_hardware": [valve_plugin, "motor-tic249"],
            "stop_required_hardware": ["motor-tic249"],
            "stop_best_effort_hardware": [valve_plugin],
        },
        "requirements": {
            "valve_actions": [valve_plugin],
            "shutdown_full_confirmation": ["motor-dri0050", valve_plugin],
            "telemetry_sc_wc": ["usb-adc-dfr1184"],
        },
        "diagnostics": {
            "hui_readiness": "/api/v1/hardware/hui/readiness",
            "hardware_diagnosis": "/api/v1/hardware/diagnosis?scan=never",
            "valve_controller": f"/api/v1/plugins/{valve_plugin}/health",
            "modbus_io": "/api/v1/plugins/modbus-io/health",
            "analog_inputs": "/api/v1/hardware/sensors/batch",
        },
    }
