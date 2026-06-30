"""HUI domain actions for OqlOS-owned hardware recipes (facade)."""

from __future__ import annotations

from typing import Any

from oqlos.hardware.hui_artificial_lung import start_hui_artificial_lung, stop_hui_artificial_lung
from oqlos.hardware.hui_hold import (
    HUI_ALL_VALVE_IDS,
    HUI_HOLD_PROFILES,
    shutdown_all_hui_hardware,
    start_hui_hold,
    stop_hui_hold,
)
from oqlos.hardware.hui_lung_recipe import (
    HUI_AL_LUNG_VALVE_ID,
    HUI_LUNG_MAX_SPEED_STEPS_PER_S,
    HUI_LUNG_PAUSE_SECONDS,
    HUI_LUNG_RAMP_SECONDS,
    HUI_LUNG_RECIPROCATE_ARGS,
    HUI_LUNG_STROKE_STEPS,
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
    "list_hui_actions",
    "shutdown_all_hui_hardware",
    "start_hui_artificial_lung",
    "start_hui_hold",
    "stop_hui_artificial_lung",
    "stop_hui_hold",
]


def list_hui_actions() -> dict[str, Any]:
    return {
        "ok": True,
        "hold_keys": list(HUI_HOLD_PROFILES.keys()),
        "al_keys": ["al-start", "al-stop"],
        "profiles": {
            key: {
                "valves_on": list(profile["valves_on"]),
                "pump_pct": profile["pump_pct"],
            }
            for key, profile in HUI_HOLD_PROFILES.items()
        },
        "artificial_lung": {
            "valve_id": HUI_AL_LUNG_VALVE_ID,
            "reciprocate_args": dict(HUI_LUNG_RECIPROCATE_ARGS),
        },
    }
