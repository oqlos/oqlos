"""HUI momentary valve actions (WC press/bleed) with MAP overrides."""

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


def _spec_from_map_action(binding: Any) -> dict[str, Any] | None:
    if not isinstance(binding, dict):
        return None
    body = binding.get("body") if isinstance(binding.get("body"), dict) else binding
    kind = str(binding.get("kind") or body.get("kind") or "").strip().lower()
    command = str(body.get("command") or "").strip().lower()
    valve_id = str(body.get("valve_id") or body.get("valveId") or "").strip()
    value = _coerce_bool(body.get("value", body.get("on", body.get("open"))))
    if value is None and command in {"valve_on", "valve-on"}:
        value = True
    if value is None and command in {"valve_off", "valve-off"}:
        value = False
    if kind not in {"hui-valve", "hui_valve"} and command not in {"hui_valve", "valve_toggle"}:
        if not valve_id or value is None:
            return None
    if not valve_id or value is None:
        return None
    return {"valve_id": valve_id, "value": value}


def _mapped_hui_valve_specs() -> dict[str, dict[str, Any]]:
    """Legacy MAP JSON/YAML actions (kind=hui-valve)."""
    try:
        from oqlos.api.hardware_mapping_store import mapping_store

        mapping = mapping_store.get()
    except Exception:
        return {}

    actions = mapping.get("actions") if isinstance(mapping.get("actions"), dict) else {}
    specs: dict[str, dict[str, Any]] = {}
    for key, binding in actions.items():
        normalized_key = _normalize_hui_valve_key(key)
        spec = _spec_from_map_action(binding)
        if normalized_key and spec is not None:
            specs[normalized_key] = spec
    return specs


def _oql_hui_valve_specs() -> dict[str, dict[str, Any]]:
    """OQL SET specs from layers/hardware/hui-profiles.oql (preferred)."""
    try:
        from oqlos.hardware.hui_profiles_oql import load_oql_hui_valve_specs

        return load_oql_hui_valve_specs()
    except Exception:
        return {}


def get_hui_valve_specs() -> dict[str, dict[str, Any]]:
    # Migration order: code defaults < MAP YAML/JSON < OQL file (source of truth).
    specs = {key: dict(value) for key, value in HUI_VALVE_DEFAULTS.items()}
    specs.update(_mapped_hui_valve_specs())
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
