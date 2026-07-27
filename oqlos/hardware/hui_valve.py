"""HUI momentary valve actions (WC press/bleed) with configuration overrides."""

from __future__ import annotations

from typing import Any

HUI_VALVE_DEFAULTS: dict[str, dict[str, Any]] = {
    "wc-press": {"valve_id": "valve-wc", "value": True},
    "wc-bleed": {"valve_id": "valve-wc", "value": False},
}


def _normalize_hui_valve_key(key: Any) -> str:
    text = str(key or "").strip().lower()
    if text.startswith("hui.valve."):
        return text.removeprefix("hui.valve.")
    return text


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"1", "true", "on", "open", "press"}:
            return True
        if token in {"0", "false", "off", "close", "bleed"}:
            return False
    return None


def _configured_hui_valve_specs() -> dict[str, dict[str, Any]]:
    try:
        from oqlos.hardware.configuration import load_effective_hardware_configuration

        config, _ = load_effective_hardware_configuration()
    except Exception:
        return {}
    hui = config.profiles.get("hui") if isinstance(config.profiles.get("hui"), dict) else {}
    valves = hui.get("valves") if isinstance(hui.get("valves"), dict) else {}
    specs: dict[str, dict[str, Any]] = {}
    for key, body in valves.items():
        if not isinstance(body, dict):
            continue
        normalized_key = _normalize_hui_valve_key(key)
        valve_id = str(body.get("valve_id") or body.get("valveId") or "").strip()
        value = _coerce_bool(body.get("value"))
        if normalized_key and valve_id and value is not None:
            specs[normalized_key] = {"valve_id": valve_id, "value": value}
    return specs


def _oql_hui_valve_specs() -> dict[str, dict[str, Any]]:
    """OQL SET specs from layers/hardware/hui-profiles.oql (preferred)."""
    try:
        from oqlos.hardware.hui_profiles_oql import load_oql_hui_valve_specs

        return load_oql_hui_valve_specs()
    except Exception:
        return {}


def get_hui_valve_specs() -> dict[str, dict[str, Any]]:
    # One normalized config model plus OQL scenario-layer overrides.
    specs = {key: dict(value) for key, value in HUI_VALVE_DEFAULTS.items()}
    specs.update(_configured_hui_valve_specs())
    specs.update(_oql_hui_valve_specs())
    return specs


def get_hui_valve_spec(key: str) -> dict[str, Any] | None:
    normalized = _normalize_hui_valve_key(key)
    return get_hui_valve_specs().get(normalized)


async def run_hui_valve_key(gateway: Any, key: str) -> dict[str, Any]:
    normalized = _normalize_hui_valve_key(key)
    spec = get_hui_valve_spec(normalized)
    if spec is None:
        return {"ok": False, "command": "valve_key", "key": normalized, "error": f"Unknown HUI valve key: {key}"}

    valve_id = str(spec["valve_id"])
    value = bool(spec["value"])
    result = await gateway.set_valve(valve_id, value)
    ok = bool(result) if isinstance(result, bool) else bool((result or {}).get("success", result))
    return {
        "ok": ok,
        "command": "valve_key",
        "key": normalized,
        "valve_id": valve_id,
        "value": value,
        "result": result,
    }
