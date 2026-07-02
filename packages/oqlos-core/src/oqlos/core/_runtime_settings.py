"""Lightweight runtime settings for oqlos-core (no pydantic-settings / FastAPI)."""

from __future__ import annotations

import os


def lung_motor_url() -> str:
    return (
        os.environ.get("LUNG_MOTOR_URL")
        or os.environ.get("OQLOS_LUNG_MOTOR_URL")
        or "http://localhost:8203"
    ).rstrip("/")


def pump_flow_full_scale_lpm(default: float = 10.0) -> float:
    raw = os.environ.get("PUMP_FLOW_FULL_SCALE_LPM") or os.environ.get("OQLOS_PUMP_FLOW_FULL_SCALE_LPM")
    if raw is not None:
        try:
            value = float(str(raw).replace(",", ".").strip())
            if value > 0:
                return value
        except Exception:
            pass
    try:
        from oqlos.config import get_settings

        value = float(getattr(get_settings(), "pump_flow_full_scale_lpm", default))
        return value if value > 0 else default
    except Exception:
        return default
