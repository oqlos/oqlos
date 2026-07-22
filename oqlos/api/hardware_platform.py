"""Runtime platform detection for hardware health/identify."""

from __future__ import annotations

import glob
import os
import platform
import sys
from typing import Any

from oqlos.api import hardware_modbus_topology as topology
from oqlos.config import get_settings
from oqlos.hardware.discovery import list_serial_ports
from oqlos.shared.file_ops import read_text_file_or_empty as _read_text_file

_settings = get_settings()


def _board_model() -> str:
    return " ".join(
        filter(
            None,
            [
                _read_text_file("/proc/device-tree/model"),
                _read_text_file("/sys/firmware/devicetree/base/model"),
            ],
        )
    ).strip()


def _is_raspberry_pi_host() -> bool:
    return "raspberry pi" in _board_model().lower()


def _os_release() -> dict[str, str]:
    data = {}
    for line in _read_text_file("/etc/os-release").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.lower()] = value.strip().strip('"')
    return data


def _in_container() -> bool:
    if os.path.exists("/.dockerenv"):
        return True
    cgroup = _read_text_file("/proc/1/cgroup").lower()
    return any(
        marker in cgroup for marker in ("docker", "containerd", "kubepods", "podman")
    )


def _selected_hardware_platform() -> str:
    value = (
        os.getenv("OQLOS_HARDWARE_PLATFORM")
        or os.getenv("HARDWARE_PLATFORM")
        or os.getenv("PIADC_PLATFORM")
        or os.getenv("ADS1115_PLATFORM")
        or "auto"
    )
    value = value.strip().lower().replace("_", "-")
    aliases = {
        "pc": "desktop",
        "desktop-linux": "desktop",
        "rpi": "raspberry-pi",
        "raspberry": "raspberry-pi",
        "raspberrypi": "raspberry-pi",
        "remote-rpi": "external-rpi",
        "external": "external-rpi",
        "smbus": "generic-linux",
        "linux-smbus": "generic-linux",
    }
    return aliases.get(value, value)


def _selected_piadc_platform() -> str:
    value = (
        os.getenv("PIADC_PLATFORM")
        or os.getenv("ADS1115_PLATFORM")
        or _selected_hardware_platform()
    )
    value = value.strip().lower().replace("_", "-")
    aliases = {
        "rpi": "raspberry-pi",
        "raspberry": "raspberry-pi",
        "raspberrypi": "raspberry-pi",
        "remote-rpi": "external-rpi",
        "external": "external-rpi",
        "smbus": "generic-linux",
        "linux-smbus": "generic-linux",
        "pc": "desktop",
    }
    return aliases.get(value, value)


def _selected_adc_source() -> str:
    value = (
        os.getenv("OQLOS_ADC_SOURCE")
        or os.getenv("ADC_SOURCE")
        or _settings.adc_source
        or "auto"
    )
    normalized = str(value).strip().lower()
    return (
        normalized if normalized in {"auto", "usb-adc-stack", "modbus-adc"} else "auto"
    )


def _classify_platform_type(
    system: str, is_rpi: bool, in_container: bool, is_wsl: bool
) -> str:
    """Map detected OS attributes to a canonical platform type string."""
    if is_rpi:
        return "raspberry-pi"
    if system == "Linux" and in_container:
        return "linux-container"
    if system == "Linux" and is_wsl:
        return "wsl"
    if system == "Linux":
        return "desktop-linux"
    if system == "Darwin":
        return "macos"
    if system == "Windows":
        return "windows"
    return "unknown"


def _detect_runtime_platform() -> dict[str, Any]:
    board_model = _board_model()
    os_release = _os_release()
    system = platform.system() or "unknown"
    is_wsl = "microsoft" in platform.release().lower()
    in_container = _in_container()
    is_rpi = "raspberry pi" in board_model.lower()

    detected = _classify_platform_type(system, is_rpi, in_container, is_wsl)

    piadc_selected = _selected_piadc_platform()
    adc_source = _selected_adc_source()
    usb_adc_selected = adc_source == "usb-adc-stack"
    modbus_ports = topology._modbus_runtime_serial_ports()
    modbus_io_serial = modbus_ports["io_serial_port"]
    modbus_adc_serial = modbus_ports["adc_serial_port"]
    serial_ports_error = ""
    try:
        serial_ports = [port.get("device") for port in list_serial_ports()]
    except RuntimeError as exc:
        serial_ports = []
        serial_ports_error = str(exc)

    payload = {
        "selected": _selected_hardware_platform(),
        "piadc_selected": piadc_selected,
        "modbus_adc_selected": "disabled" if usb_adc_selected else "modbus-rtu",
        "detected": detected,
        "is_raspberry_pi": is_rpi,
        "raspberry_pi_model": board_model if is_rpi else "",
        "board_model": board_model,
        "system": system,
        "os_pretty_name": os_release.get("pretty_name", ""),
        "os_id": os_release.get("id", ""),
        "os_version": os_release.get("version_id", ""),
        "kernel": platform.release(),
        "machine": platform.machine() or "unknown",
        "python": sys.version.split()[0],
        "in_container": in_container,
        "is_wsl": is_wsl,
        "analog_input_driver_role": "usb-adc-stack"
        if usb_adc_selected
        else "modbus-rtu",
        "modbus_topology": modbus_ports["topology"],
        "modbus_topology_mode": modbus_ports["topology_mode"],
        "modbus_bus_serial_port": modbus_ports.get("shared_serial_port")
        or (modbus_io_serial if modbus_io_serial == modbus_adc_serial else ""),
        "modbus_io_serial_port": modbus_io_serial,
        "modbus_adc_driver_role": "disabled" if usb_adc_selected else "modbus-rtu",
        "modbus_adc_serial_port": modbus_adc_serial,
        "modbus_adc_local_probe_allowed": not usb_adc_selected,
        "piadc_driver_role": (
            "replaced-by-usb-adc-stack"
            if usb_adc_selected
            else "replaced-by-modbus-adc"
        ),
        "piadc_local_probe_allowed": False,
        "i2c_buses": sorted(glob.glob("/dev/i2c-*")),
        "serial_ports": serial_ports,
    }
    if serial_ports_error:
        payload["serial_ports_error"] = serial_ports_error
    return payload
