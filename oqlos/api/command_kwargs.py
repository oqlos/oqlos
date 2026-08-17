"""Normalize command kwargs that callers send as ``args`` or ``params``.

Plugin execute historically documented ``params``; CQRS / OQL / MQTT / lung+RTC
use ``args``. Reading only one key made valves look like Modbus failures and
made coil writes silently use defaults.
"""

from __future__ import annotations

from typing import Any, Mapping


def resolve_args_or_params(
    payload: Mapping[str, Any] | None,
    *,
    prefer: str = "params",
) -> dict[str, Any]:
    """Return a dict from ``params`` and/or ``args``.

    ``prefer`` selects which non-empty dict wins when both are present.
    Empty dicts fall through to the other key so ``{"params": {}, "args": {...}}``
    still works for legacy callers.
    """
    data = payload or {}
    params = data.get("params")
    args = data.get("args")
    primary = params if prefer == "params" else args
    secondary = args if prefer == "params" else params
    if isinstance(primary, dict) and primary:
        return dict(primary)
    if isinstance(secondary, dict) and secondary:
        return dict(secondary)
    if isinstance(primary, dict):
        return dict(primary)
    if isinstance(secondary, dict):
        return dict(secondary)
    return {}


def validate_args_or_params_types(
    payload: Mapping[str, Any] | None,
    *,
    prefer: str = "args",
) -> dict[str, Any]:
    """Like :func:`resolve_args_or_params` but reject non-object values.

    Returns ``(ok_dict,)`` semantics via raising ``ValueError`` with the bad
    field name so HTTP layers can map to Problem Details.
    """
    data = payload or {}
    for field in ("args", "params"):
        value = data.get(field, None)
        if value is None:
            continue
        if not isinstance(value, dict):
            raise ValueError(field)
    return resolve_args_or_params(data, prefer=prefer)


def pick_param(
    params: Mapping[str, Any] | None,
    *keys: str,
    default: Any = None,
) -> Any:
    """Return the first present key among snake/camel aliases."""
    data = params or {}
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default

