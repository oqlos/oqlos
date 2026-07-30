"""Modbus baud helpers, operator profiles, and target speed persistence."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODBUS_BASELINE_BAUD = 4800
MODBUS_TARGET_BAUD_OPTIONS = (4800, 9600, 19200, 38400, 57600, 115200)
MODBUS_PROFILE_IDS = ("modbus-adc", "modbus-io", "shared-bus")

_USER_SETTINGS: dict[str, Any] | None = None


def _state_dir() -> Path:
    raw = os.getenv("OQLOS_STATE_DIR", "").strip()
    if raw:
        return Path(raw)
    return Path.home() / ".local" / "state" / "oqlos"


def _settings_file() -> Path:
    return _state_dir() / "modbus-user-settings.json"


def normalize_target_baud(value: int | str | None, *, default: int = MODBUS_BASELINE_BAUD) -> int:
    try:
        baud = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return baud if baud in MODBUS_TARGET_BAUD_OPTIONS else default


def build_init_baud_sequence(target_baud: int | None) -> list[int]:
    """Commissioning order: always probe baseline 4800, then target speed."""
    target = normalize_target_baud(target_baud)
    if target == MODBUS_BASELINE_BAUD:
        return [MODBUS_BASELINE_BAUD]
    return [MODBUS_BASELINE_BAUD, target]


def normalize_probe_baudrates(requested: list[int] | None, target_baud: int) -> list[int]:
    ordered: list[int] = []
    for value in [MODBUS_BASELINE_BAUD, *(requested or []), normalize_target_baud(target_baud)]:
        baud = normalize_target_baud(value, default=0)
        if baud <= 0 or baud in ordered:
            continue
        ordered.append(baud)
    return ordered or [MODBUS_BASELINE_BAUD]


def _load_user_settings() -> dict[str, Any]:
    global _USER_SETTINGS
    if _USER_SETTINGS is not None:
        return _USER_SETTINGS
    path = _settings_file()
    if not path.exists():
        _USER_SETTINGS = {}
        return _USER_SETTINGS
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    _USER_SETTINGS = payload if isinstance(payload, dict) else {}
    return _USER_SETTINGS


def _save_user_settings(payload: dict[str, Any]) -> None:
    global _USER_SETTINGS
    path = _settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _USER_SETTINGS = payload


def _topology_module():
    from oqlos.api import hardware_modbus_topology as topology

    return topology


def _runtime_serial_ports() -> dict[str, Any]:
    return _topology_module()._modbus_runtime_serial_ports()


def _default_active_profile(ports: dict[str, Any]) -> str:
    if ports.get("topology") == "shared-bus":
        return "shared-bus"
    # Prefer IO on multi-adapter stands (valves/HUI). ADC-only was a misleading
    # default that left the wizard on the wrong profile after first visit.
    return "modbus-io"


def _profile_default_serial_port(profile_id: str, ports: dict[str, Any], settings: Any) -> str:
    if profile_id == "modbus-adc":
        return str(ports.get("adc_serial_port") or getattr(settings, "modbus_adc_serial_port", "") or "").strip()
    if profile_id == "modbus-io":
        return str(ports.get("io_serial_port") or getattr(settings, "modbus_serial_port", "") or "").strip()
    shared = str(ports.get("shared_serial_port") or ports.get("io_serial_port") or "").strip()
    if shared:
        return shared
    return str(getattr(settings, "modbus_serial_port", "") or "").strip()


def _profile_default_baud(profile_id: str, settings: Any) -> int:
    if profile_id == "modbus-adc":
        return normalize_target_baud(getattr(settings, "modbus_adc_baud", MODBUS_BASELINE_BAUD))
    return normalize_target_baud(getattr(settings, "modbus_baud", MODBUS_BASELINE_BAUD))


def _profile_default_parity(profile_id: str, settings: Any) -> str:
    attribute = "modbus_adc_parity" if profile_id == "modbus-adc" else "modbus_parity"
    parity = str(getattr(settings, attribute, "N") or "N").upper()
    return parity if parity in {"N", "E", "O"} else "N"


def _profile_device_ids(profile_id: str, settings: Any) -> list[int]:
    topology = _topology_module()
    io_ids = topology._modbus_io_device_ids()
    adc_id = int(getattr(settings, "modbus_adc_device_id", 0) or 0)
    if profile_id == "modbus-adc":
        return [adc_id] if adc_id > 0 else []
    if profile_id == "modbus-io":
        return io_ids
    merged = list(io_ids)
    if adc_id > 0 and adc_id not in merged:
        merged.append(adc_id)
    return sorted(merged)


def _profile_topology(profile_id: str) -> str:
    if profile_id == "shared-bus":
        return "shared-bus"
    return "separate-adapters"


def _profile_module_roles(profile_id: str) -> list[str]:
    if profile_id == "modbus-adc":
        return ["modbus-adc"]
    if profile_id == "modbus-io":
        return ["modbus-io"]
    return ["modbus-io", "modbus-adc"]


def _merge_profile_config(profile_id: str, settings: Any, ports: dict[str, Any]) -> dict[str, Any]:
    user = _load_user_settings()
    persisted = (user.get("profiles") or {}).get(profile_id) or {}
    if not isinstance(persisted, dict):
        persisted = {}
    target = normalize_target_baud(
        persisted.get("target_baudrate"),
        default=_profile_default_baud(profile_id, settings),
    )
    serial_override = str(persisted.get("serial_port") or "").strip()
    # Drop stale overrides that point at missing devices (e.g. unplugged FTDI
    # by-id, or historical by-path that now maps to the motor CH340).
    if serial_override:
        try:
            if not Path(serial_override).exists():
                serial_override = ""
        except OSError:
            serial_override = ""
    serial_port = serial_override or _profile_default_serial_port(profile_id, ports, settings)
    parity = str(persisted.get("target_parity") or _profile_default_parity(profile_id, settings)).upper()
    return {
        "profile_id": profile_id,
        "topology": _profile_topology(profile_id),
        "module_roles": _profile_module_roles(profile_id),
        "serial_port": serial_port,
        "serial_port_override": serial_override,
        "target_baudrate": target,
        "target_parity": parity,
        "device_ids": _profile_device_ids(profile_id, settings),
        "baseline_baudrate": MODBUS_BASELINE_BAUD,
        "baud_probe_sequence": build_init_baud_sequence(target),
    }


def active_modbus_profile_id(settings: Any | None = None) -> str:
    user = _load_user_settings()
    ports = _runtime_serial_ports()
    active = str(user.get("active_profile") or "").strip()
    if active in MODBUS_PROFILE_IDS:
        return active
    return _default_active_profile(ports)


def profile_modbus_target_baud(settings: Any, profile_id: str | None = None) -> int:
    pid = profile_id or active_modbus_profile_id(settings)
    if pid not in MODBUS_PROFILE_IDS:
        pid = "modbus-adc"
    user = _load_user_settings()
    profile = (user.get("profiles") or {}).get(pid) or {}
    if isinstance(profile, dict) and profile.get("target_baudrate") is not None:
        return normalize_target_baud(profile["target_baudrate"], default=_profile_default_baud(pid, settings))
    legacy = user.get("target_baudrate")
    if legacy is not None and pid in {active_modbus_profile_id(settings), "modbus-io", "shared-bus"}:
        return normalize_target_baud(legacy, default=_profile_default_baud(pid, settings))
    return _profile_default_baud(pid, settings)


def effective_modbus_target_baud(settings: Any) -> int:
    return profile_modbus_target_baud(settings, active_modbus_profile_id(settings))


def effective_modbus_adc_target_baud(settings: Any) -> int:
    active = active_modbus_profile_id(settings)
    if active == "modbus-adc":
        return profile_modbus_target_baud(settings, "modbus-adc")
    if active == "shared-bus":
        return profile_modbus_target_baud(settings, "shared-bus")
    user = _load_user_settings()
    override = user.get("target_adc_baudrate", user.get("target_baudrate"))
    if override is not None:
        return normalize_target_baud(override, default=int(getattr(settings, "modbus_adc_baud", MODBUS_BASELINE_BAUD)))
    profile_baud = profile_modbus_target_baud(settings, "modbus-adc")
    if profile_baud != MODBUS_BASELINE_BAUD or (user.get("profiles") or {}).get("modbus-adc"):
        return profile_baud
    return normalize_target_baud(getattr(settings, "modbus_adc_baud", MODBUS_BASELINE_BAUD))


def read_modbus_baud_settings(settings: Any) -> dict[str, Any]:
    ports = _runtime_serial_ports()
    active = active_modbus_profile_id(settings)
    profiles = {pid: _merge_profile_config(pid, settings, ports) for pid in MODBUS_PROFILE_IDS}
    active_cfg = profiles[active]
    target = active_cfg["target_baudrate"]
    adc_target = effective_modbus_adc_target_baud(settings)
    return {
        "ok": True,
        "active_profile": active,
        "profiles": profiles,
        "baseline_baudrate": MODBUS_BASELINE_BAUD,
        "target_baudrate": target,
        "target_adc_baudrate": adc_target,
        "target_parity": active_cfg["target_parity"],
        "baudrate_options": list(MODBUS_TARGET_BAUD_OPTIONS),
        "baud_probe_sequence": active_cfg["baud_probe_sequence"],
        "note": "Init probes start at the machine baseline 4800 baud, then switch to the selected target speed.",
        "persisted": bool(_load_user_settings()),
        "settings_path": str(_settings_file()),
    }


def write_modbus_baud_settings(settings: Any, payload: dict[str, Any]) -> dict[str, Any]:
    user = dict(_load_user_settings())
    profiles: dict[str, Any] = dict(user.get("profiles") or {})
    profile_id = str(payload.get("profile_id") or user.get("active_profile") or active_modbus_profile_id(settings))
    if profile_id not in MODBUS_PROFILE_IDS:
        profile_id = active_modbus_profile_id(settings)

    if payload.get("active_profile") in MODBUS_PROFILE_IDS:
        user["active_profile"] = payload["active_profile"]

    existing = dict(profiles.get(profile_id) or {})
    if "target_baudrate" in payload:
        existing["target_baudrate"] = normalize_target_baud(
            payload.get("target_baudrate"),
            default=profile_modbus_target_baud(settings, profile_id),
        )
    if "serial_port" in payload:
        existing["serial_port"] = str(payload.get("serial_port") or "").strip()
    if "target_parity" in payload:
        existing["target_parity"] = str(payload.get("target_parity") or "N").upper()

    profiles[profile_id] = existing
    user["profiles"] = profiles
    user["target_baudrate"] = existing.get("target_baudrate", user.get("target_baudrate"))
    user["target_adc_baudrate"] = existing.get("target_baudrate", user.get("target_adc_baudrate"))
    user["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_user_settings(user)
    return read_modbus_baud_settings(settings)


def clear_modbus_baud_user_settings_cache() -> None:
    global _USER_SETTINGS
    _USER_SETTINGS = None


def runtime_modbus_plugin_overrides(settings: Any, plugin_id: str) -> dict[str, Any]:
    """Resolve one plugin's effective RTU settings from the persisted operator profile."""
    if plugin_id not in {"modbus-io", "modbus-adc"}:
        return {}
    active = active_modbus_profile_id(settings)
    profile_id = "shared-bus" if active == "shared-bus" else plugin_id
    profile = _merge_profile_config(profile_id, settings, _runtime_serial_ports())
    device_ids = _profile_device_ids(plugin_id, settings)
    overrides: dict[str, Any] = {
        "serial_port": profile["serial_port"],
        "baudrate": profile["target_baudrate"],
        "parity": profile["target_parity"],
    }
    if device_ids:
        overrides["device_id"] = device_ids[0]
    return {key: value for key, value in overrides.items() if value not in (None, "")}


def apply_modbus_runtime_settings(
    settings: Any,
    plugin_configs: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Apply persisted Modbus profiles to gateway configs and report effective values."""
    applied: dict[str, dict[str, Any]] = {}
    for plugin_id in ("modbus-io", "modbus-adc"):
        config = plugin_configs.get(plugin_id)
        if config is None or getattr(config, "connection_type", "") != "modbus-rtu":
            continue
        overrides = runtime_modbus_plugin_overrides(settings, plugin_id)
        config.connection_params.update(overrides)
        applied[plugin_id] = dict(overrides)
    return applied
