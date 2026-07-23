"""Compatibility wrappers for shared Modbus discovery helpers.

The actual Waveshare Modbus RTU probing lives in the oqlos/pimodbus
library so firmware, diagnostics and c2004 use one implementation.
"""

from __future__ import annotations

import os
import pathlib
import sys
from typing import Any, Callable


def _ensure_local_pimodbus_on_path() -> None:
    """Allow source-tree development without publishing pimodbus first."""
    try:
        import pimodbus  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    # /home/tom/github/oqlos/oqlos/oqlos/hardware/discovery.py
    # -> /home/tom/github + oqlos/pimodbus
    try:
        github_root = pathlib.Path(__file__).resolve().parents[4]
    except IndexError:
        return
    candidate = github_root / "oqlos" / "pimodbus"
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


_MODBUS_PROBE_SPECS: dict[str, dict[str, Any]] = {
    "modbus-io": {
        "probe_fn": probe_modbus_io,
        "default_serial": DEFAULT_MODBUS_SERIAL,
        "default_baud": DEFAULT_MODBUS_BAUD,
        "default_parity": DEFAULT_MODBUS_PARITY,
        "default_device_id": DEFAULT_MODBUS_DEVICE_ID,
    },
    "modbus-adc": {
        "probe_fn": probe_modbus_adc,
        "default_serial": DEFAULT_MODBUS_ADC_SERIAL,
        "default_baud": DEFAULT_MODBUS_ADC_BAUD,
        "default_parity": DEFAULT_MODBUS_ADC_PARITY,
        "default_device_id": DEFAULT_MODBUS_ADC_DEVICE_ID,
        "read_address": DEFAULT_MODBUS_ADC_READ_ADDRESS,
        "read_count": DEFAULT_MODBUS_ADC_READ_COUNT,
    },
}


def _probe_waveshare(
    probe_fn: Any,
    *,
    preferred_port: str | None,
    preferred_baud: int | None,
    preferred_parity: str | None,
    preferred_device_id: int | None,
    default_serial: str,
    default_baud: int,
    default_parity: str,
    default_device_id: int,
    timeout: float,
    **extra: Any,
) -> dict[str, Any]:
    return probe_fn(
        serial_port=preferred_port or default_serial,
        baudrate=preferred_baud or default_baud,
        parity=preferred_parity or default_parity,
        device_id=preferred_device_id or default_device_id,
        timeout=timeout,
        ports=list_serial_ports(),
        **extra,
    )


def _probe_waveshare_role(
    role: str,
    preferred_port: str | None,
    preferred_baud: int | None,
    preferred_parity: str | None,
    preferred_device_id: int | None,
    timeout: float,
) -> dict[str, Any]:
    spec = _MODBUS_PROBE_SPECS[role]
    extra = {
        key: spec[key]
        for key in ("read_address", "read_count")
        if key in spec
    }
    return _probe_waveshare(
        spec["probe_fn"],
        preferred_port=preferred_port,
        preferred_baud=preferred_baud,
        preferred_parity=preferred_parity,
        preferred_device_id=preferred_device_id,
        default_serial=spec["default_serial"],
        default_baud=spec["default_baud"],
        default_parity=spec["default_parity"],
        default_device_id=spec["default_device_id"],
        timeout=timeout,
        **extra,
    )


def _build_waveshare_probe(role: str, doc: str) -> Callable[..., dict[str, Any]]:
    def _probe(
        preferred_port: str | None = None,
        preferred_baud: int | None = None,
        preferred_parity: str | None = None,
        preferred_device_id: int | None = None,
        timeout: float = 0.35,
    ) -> dict[str, Any]:
        return _probe_waveshare_role(role, preferred_port, preferred_baud, preferred_parity, preferred_device_id, timeout)

    _probe.__doc__ = doc
    return _probe


probe_waveshare_modbus = _build_waveshare_probe(
    "modbus-io",
    "Probe serial ports and return the first working Modbus IO configuration.",
)
probe_waveshare_modbus_adc = _build_waveshare_probe(
    "modbus-adc",
    "Probe serial ports for the Waveshare Modbus RTU Analog Input 8CH module.",
)
