"""Compatibility wrappers for shared Modbus discovery helpers.

The actual Waveshare Modbus RTU probing lives in the maskservice/pimodbus
library so firmware, diagnostics and c2004 use one implementation.
"""

from __future__ import annotations

import os
import pathlib
import sys
from typing import Any


def _ensure_local_pimodbus_on_path() -> None:
    """Allow source-tree development without publishing pimodbus first."""
    try:
        import pimodbus  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    # /home/tom/github/oqlos/oqlos/oqlos/hardware/discovery.py
    # -> /home/tom/github + maskservice/pimodbus
    try:
        github_root = pathlib.Path(__file__).resolve().parents[4]
    except IndexError:
        return
    candidate = github_root / "maskservice" / "pimodbus"
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


_ensure_local_pimodbus_on_path()

try:
    from pimodbus.discovery import list_serial_ports, probe_modbus_adc, probe_modbus_io  # noqa: E402
except ModuleNotFoundError as _exc:  # pragma: no cover - optional hardware dependency
    # ``pimodbus`` is an external sibling library: present on hardware nodes (added to
    # PYTHONPATH at deploy) but not bundled in API-only/Docker/mock deployments. Defer
    # the failure to call time so importing this module — and thus the whole API — does
    # not crash where real Modbus probing is never used.
    _PIMODBUS_IMPORT_ERROR = _exc

    def _pimodbus_unavailable(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError(
            "Modbus discovery needs the 'pimodbus' package, which is not installed. "
            "Install it or add it to PYTHONPATH (hardware nodes do this at deploy). "
            "Mock mode and non-Modbus features work without it."
        ) from _PIMODBUS_IMPORT_ERROR

    list_serial_ports = _pimodbus_unavailable  # type: ignore[assignment]
    probe_modbus_adc = _pimodbus_unavailable  # type: ignore[assignment]
    probe_modbus_io = _pimodbus_unavailable  # type: ignore[assignment]

DEFAULT_MODBUS_SERIAL = os.getenv("MODBUS_SERIAL_PORT") or os.getenv("MODBUS_BUS_SERIAL_PORT") or "/dev/ttyACM1"
DEFAULT_MODBUS_BAUD = int(os.getenv("MODBUS_BAUD") or os.getenv("MODBUS_BUS_BAUD") or "9600")
DEFAULT_MODBUS_PARITY = (os.getenv("MODBUS_PARITY") or os.getenv("MODBUS_BUS_PARITY") or "N").upper()
DEFAULT_MODBUS_DEVICE_ID = int(os.getenv("MODBUS_DEVICE_ID", "1"))
DEFAULT_MODBUS_ADC_SERIAL = os.getenv("MODBUS_ADC_SERIAL_PORT") or os.getenv("MODBUS_BUS_SERIAL_PORT") or "/dev/ttyUSB0"
DEFAULT_MODBUS_ADC_BAUD = int(os.getenv("MODBUS_ADC_BAUD") or os.getenv("MODBUS_BUS_BAUD") or "9600")
DEFAULT_MODBUS_ADC_PARITY = (os.getenv("MODBUS_ADC_PARITY") or os.getenv("MODBUS_BUS_PARITY") or "N").upper()
DEFAULT_MODBUS_ADC_DEVICE_ID = int(os.getenv("MODBUS_ADC_DEVICE_ID", "2"))
DEFAULT_MODBUS_ADC_READ_ADDRESS = int(os.getenv("MODBUS_ADC_READ_ADDRESS", "0"))
DEFAULT_MODBUS_ADC_READ_COUNT = int(os.getenv("MODBUS_ADC_READ_COUNT", "8"))


def probe_waveshare_modbus(
    preferred_port: str | None = None,
    preferred_baud: int | None = None,
    preferred_parity: str | None = None,
    preferred_device_id: int | None = None,
    timeout: float = 0.35,
) -> dict[str, Any]:
    """Probe serial ports and return the first working Modbus IO configuration."""
    return probe_modbus_io(
        serial_port=preferred_port or DEFAULT_MODBUS_SERIAL,
        baudrate=preferred_baud or DEFAULT_MODBUS_BAUD,
        parity=preferred_parity or DEFAULT_MODBUS_PARITY,
        device_id=preferred_device_id or DEFAULT_MODBUS_DEVICE_ID,
        timeout=timeout,
        ports=list_serial_ports(),
    )


def probe_waveshare_modbus_adc(
    preferred_port: str | None = None,
    preferred_baud: int | None = None,
    preferred_parity: str | None = None,
    preferred_device_id: int | None = None,
    timeout: float = 0.35,
) -> dict[str, Any]:
    """Probe serial ports for the Waveshare Modbus RTU Analog Input 8CH module."""
    return probe_modbus_adc(
        serial_port=preferred_port or DEFAULT_MODBUS_ADC_SERIAL,
        baudrate=preferred_baud or DEFAULT_MODBUS_ADC_BAUD,
        parity=preferred_parity or DEFAULT_MODBUS_ADC_PARITY,
        device_id=preferred_device_id or DEFAULT_MODBUS_ADC_DEVICE_ID,
        timeout=timeout,
        read_address=DEFAULT_MODBUS_ADC_READ_ADDRESS,
        read_count=DEFAULT_MODBUS_ADC_READ_COUNT,
        ports=list_serial_ports(),
    )
