"""OqlOS hardware control proxy — contract from c2004-hardware-client."""

from __future__ import annotations

import os
import pathlib
import sys


def _ensure_local_hardware_client_on_path() -> None:
    """Allow source-tree development without publishing hardware_client first."""
    try:
        import hardware_client  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    explicit = os.getenv("OQLOS_HARDWARE_CLIENT_SRC")
    if explicit and pathlib.Path(explicit).exists() and explicit not in sys.path:
        sys.path.insert(0, explicit)
        return

    try:
        github_root = pathlib.Path(__file__).resolve().parents[4]
    except IndexError:
        return
    candidate = github_root / "maskservice" / "c2004" / "packages" / "hardware-client-py" / "src"
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


_ensure_local_hardware_client_on_path()

from hardware_client.config import OqlosHardwareProxyConfig, candidate_oqlos_bases, float_from_env
from hardware_client.constants import (
    ARTIFICIAL_LUNG_IDS,
    DEFAULT_OQLOS_API_BASE,
    FALLBACK_ADAPTERS,
    MODBUS_ALLOWED_VALVE_IDS,
    PERIPHERAL_STATUS_COMMANDS,
    PERIPHERAL_STATUS_PLUGIN_ALIASES,
)
from hardware_client.errors import HardwareProxyError, is_oqlos_unavailable, oqlos_error_detail
from hardware_client.proxy import OqlosHardwareProxy as _BaseOqlosHardwareProxy
from hardware_client.resolvers import (
    extract_command_failure,
    normalize_modbus_valve_id,
    resolve_artificial_lung_target,
    resolve_diagnostic_target,
    resolve_lung_target,
    resolve_modbus_adc_target,
    resolve_modbus_target,
    resolve_pump_target,
    resolve_rtc_target,
)

# Legacy alias used inside OqlOS.
PERIPHERAL_PLUGIN_ALIASES = PERIPHERAL_STATUS_PLUGIN_ALIASES
_ARTIFICIAL_LUNG_IDS = ARTIFICIAL_LUNG_IDS
_DEFAULT_OQLOS_API_BASE = DEFAULT_OQLOS_API_BASE


class OqlosHardwareProxy(_BaseOqlosHardwareProxy):
    """OqlOS-local proxy label for unavailable identify payloads."""

    def __init__(
        self,
        config: OqlosHardwareProxyConfig | None = None,
        *,
        client=None,
    ) -> None:
        super().__init__(config, client=client, unavailable_source="oqlos.hardware.control_proxy")


__all__ = [
    "ARTIFICIAL_LUNG_IDS",
    "FALLBACK_ADAPTERS",
    "HardwareProxyError",
    "MODBUS_ALLOWED_VALVE_IDS",
    "OqlosHardwareProxy",
    "OqlosHardwareProxyConfig",
    "PERIPHERAL_PLUGIN_ALIASES",
    "PERIPHERAL_STATUS_COMMANDS",
    "candidate_oqlos_bases",
    "extract_command_failure",
    "float_from_env",
    "is_oqlos_unavailable",
    "normalize_modbus_valve_id",
    "oqlos_error_detail",
    "resolve_artificial_lung_target",
    "resolve_diagnostic_target",
    "resolve_lung_target",
    "resolve_modbus_adc_target",
    "resolve_modbus_target",
    "resolve_pump_target",
    "resolve_rtc_target",
]
