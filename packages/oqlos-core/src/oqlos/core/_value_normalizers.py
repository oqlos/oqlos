"""
Value normalization utilities for CQL interpreter.

Handles conversion of DSL command values to normalized hardware values.
"""

from __future__ import annotations

from typing import Any

from oqlos.core._runtime_settings import lung_motor_url, pump_flow_full_scale_lpm
from oqlos.core._dsl_helpers import _parse_numeric_value


class ValueNormalizer:
    """Normalizes DSL values to hardware-compatible formats."""

    def __init__(self, vars_store: Any):
        """
        Initialize with variable store for interpolation.

        Args:
            vars_store: VariableStore instance for value interpolation
        """
        self.vars = vars_store

    @staticmethod
    def coerce_float(value: Any) -> float | None:
        """Best-effort float coercion for config values."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        parsed = _parse_numeric_value(str(value))
        if parsed is not None:
            return float(parsed)
        try:
            return float(str(value).replace(",", ".").strip())
        except Exception:
            return None

    def _get_pump_flow_full_scale_lpm(self) -> float:
        """Resolve the flow rate that maps to 100% PWM."""
        for key in ("PUMP_FLOW_FULL_SCALE_LPM", "pump_flow_full_scale_lpm"):
            raw = self.vars.get(key)
            scale = self.coerce_float(raw)
            if scale and scale > 0:
                return scale

        try:
            scale = self.coerce_float(pump_flow_full_scale_lpm())
            if scale and scale > 0:
                return scale
        except Exception:
            pass

        return 10.0

    def normalize_pump_power(self, raw_value: str) -> float:
        """Convert a pump command value to a PWM percentage."""
        text = self.vars.interpolate((raw_value or "").strip())
        lowered = text.lower().strip()

        if lowered in {"on", "true"}:
            return 100.0
        if lowered in {"off", "false"}:
            return 0.0

        numeric = self.coerce_float(text)
        if numeric is None:
            return 0.0

        compact = lowered.replace(" ", "")
        if "l/min" in compact or compact.endswith("lpm") or (compact.endswith("l") and not compact.endswith("ml")):
            scale = self._get_pump_flow_full_scale_lpm()
            if scale <= 0:
                return 0.0
            numeric = numeric / scale * 100.0

        return max(0.0, min(100.0, float(numeric)))

    def normalize_valve_value(self, raw_value: Any) -> bool:
        """Convert a valve command value to a boolean state."""
        if isinstance(raw_value, bool):
            return raw_value
        if isinstance(raw_value, (int, float)):
            return float(raw_value) != 0.0

        text = self.vars.interpolate(str(raw_value or "")).strip().lower()
        if text in {"on", "true", "open", "1", "yes"}:
            return True
        if text in {"off", "false", "closed", "close", "0", "no"}:
            return False

        numeric = self.coerce_float(text)
        if numeric is not None:
            return numeric != 0.0
        return bool(text)

    def normalize_lung_value(self, raw_value: Any) -> int:
        """Convert a lung command value to a cycle count."""
        text = self.vars.interpolate(str(raw_value or "")).strip().lower()
        if text in {"off", "false", "stop", "0"}:
            return 0

        numeric = self.coerce_float(text)
        if numeric is None:
            return 5
        return max(0, int(numeric))

    def coerce_generic_peripheral_value(self, value: Any) -> Any:
        """Best-effort coercion for unmapped peripherals."""
        if not isinstance(value, str):
            return value

        lowered = value.lower()
        if lowered in {"on", "true"}:
            return 1
        if lowered in {"off", "false"}:
            return 0

        numeric = self.coerce_float(value)
        if numeric is None:
            return value
        return int(numeric) if numeric.is_integer() else numeric
