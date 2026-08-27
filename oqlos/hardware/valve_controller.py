"""Which plugin drives the valves.

Valves used to be hard-wired to the Waveshare ``modbus-io`` module. The M5Stack
``io-m5-4in8out`` module is the intended replacement, so the controller is now
resolved from configuration instead of being baked into the gateway:

1. ``OQLOS_VALVE_CONTROLLER`` env (bench override, single plugin id),
2. ``profiles.hardware.valve_controller`` in hardware-configuration-v1
   (a single id or an ordered preference list),
3. :data:`DEFAULT_VALVE_CONTROLLER_PREFERENCE` — M5 first, Modbus as fallback.

Only *enabled* plugins are considered, so a stand that has not been rewired keeps
running on ``modbus-io`` until the M5 module is enabled in the configuration.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Iterable, Mapping

logger = logging.getLogger(__name__)

MODBUS_VALVE_CONTROLLER = "modbus-io"
M5_VALVE_CONTROLLER = "io-m5-4in8out"

#: Preference order used when configuration does not pin a controller.
DEFAULT_VALVE_CONTROLLER_PREFERENCE: tuple[str, ...] = (
    M5_VALVE_CONTROLLER,
    MODBUS_VALVE_CONTROLLER,
)

VALVE_CONTROLLER_ENV_VARS = ("OQLOS_VALVE_CONTROLLER", "C2004_VALVE_CONTROLLER")


def _normalize(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        return [part.strip() for part in values.split(",") if part.strip()]
    if isinstance(values, Iterable):
        return [str(value).strip() for value in values if str(value).strip()]
    return []


def _env_preference() -> list[str]:
    for name in VALVE_CONTROLLER_ENV_VARS:
        value = os.getenv(name)
        if value:
            return _normalize(value)
    return []


def _effective_configuration() -> Any | None:
    try:
        from oqlos.hardware.configuration import load_effective_hardware_configuration

        config, _ = load_effective_hardware_configuration()
    except Exception:
        logger.debug("Valve controller: hardware configuration unavailable", exc_info=True)
        return None
    return config


def _configured_preference() -> list[str]:
    """Read ``profiles.hardware.valve_controller`` from the effective config."""
    config = _effective_configuration()
    if config is None:
        return []

    profiles = getattr(config, "profiles", None)
    hardware = profiles.get("hardware") if isinstance(profiles, Mapping) else None
    if not isinstance(hardware, Mapping):
        return []
    return _normalize(hardware.get("valve_controller"))


def valve_controller_preference() -> list[str]:
    """Ordered controller candidates, most preferred first (no enablement filter)."""
    for source in (_env_preference(), _configured_preference()):
        if source:
            # A pinned controller still gets the remaining defaults as fallback,
            # so a mis-typed or missing module cannot leave valves unreachable.
            tail = [
                plugin_id
                for plugin_id in DEFAULT_VALVE_CONTROLLER_PREFERENCE
                if plugin_id not in source
            ]
            return [*source, *tail]
    return list(DEFAULT_VALVE_CONTROLLER_PREFERENCE)


def resolve_valve_controllers(plugin_configs: Mapping[str, Any] | None) -> list[str]:
    """Enabled controller candidates for this stand, most preferred first.

    Returns an empty list when no candidate is configured *and* enabled; callers
    should treat that as "valve hardware unavailable" rather than guessing.
    """
    candidates = valve_controller_preference()
    if not plugin_configs:
        return candidates

    enabled: list[str] = []
    for plugin_id in candidates:
        config = plugin_configs.get(plugin_id)
        if config is None:
            continue
        if getattr(config, "enabled", True):
            enabled.append(plugin_id)
    return enabled


def resolve_valve_controller(plugin_configs: Mapping[str, Any] | None) -> str:
    """Primary valve controller plugin id (falls back to ``modbus-io``)."""
    controllers = resolve_valve_controllers(plugin_configs)
    return controllers[0] if controllers else MODBUS_VALVE_CONTROLLER


def gateway_valve_controllers(gateway: Any) -> list[str]:
    """Enabled valve controllers for *gateway*, or the configured ones.

    Mock gateways used by scenarios and tests do not expose plugin configs, so
    they fall back to the configuration-level answer.
    """
    resolver = getattr(gateway, "valve_controllers", None)
    if callable(resolver):
        controllers = resolver()
        if controllers:
            return list(controllers)
        return []
    return [resolve_valve_controller_from_config()]


def resolve_valve_controller_from_config() -> str:
    """Primary valve controller for callers that have no plugin config at hand."""
    config = _effective_configuration()
    plugins = getattr(config, "plugins", None) if config is not None else None
    return resolve_valve_controller(plugins if isinstance(plugins, Mapping) else None)
