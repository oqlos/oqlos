"""Rig L/R labels to Tic249 plugin forward/reverse and physical limit switches.

Validated against artificial-lung simulator (connect-scenario runtime_python_executor):
  - forward / inhale maps to limit_max (right switch on the rig)
  - backward / exhale maps to limit_min (left switch on the rig)

Reciprocate with ``reverse_on_limit``: first leg drives toward the limit in the
start direction, then the driver reverses at the switch.
"""

from __future__ import annotations

# Rig / OQL tokens.
RIG_LEFT_ALIASES = frozenset({"left", "lewo", "reverse", "backward", "min", "limit_min"})
RIG_RIGHT_ALIASES = frozenset({"right", "prawo", "forward", "max", "limit_max"})

PLUGIN_FORWARD = "forward"
PLUGIN_REVERSE = "reverse"


def rig_direction_to_plugin(direction: str) -> str | None:
    """Map rig/OQL direction token to OqlOS motor-tic249 plugin direction."""
    token = str(direction or "").strip().lower()
    if token in RIG_LEFT_ALIASES:
        return PLUGIN_REVERSE
    if token in RIG_RIGHT_ALIASES:
        return PLUGIN_FORWARD
    return None


def apply_rig_direction_to_plugin_params(params: dict[str, object], args: dict[str, object]) -> None:
    """Set ``direction`` and ``start_direction`` on reciprocate params from rig/OQL args."""
    raw = str(
        args.get("direction")
        or args.get("start_direction")
        or args.get("startDirection")
        or ""
    ).lower()
    plugin_dir = rig_direction_to_plugin(raw)
    if plugin_dir is None:
        return
    params["direction"] = plugin_dir
    params["start_direction"] = plugin_dir
