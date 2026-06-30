"""Local hardware detection probes for the doctor CLI."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from oqlos.hardware.config_paths import resolve_oqlos_config_path
from oqlos.hardware.plugins.registry import PluginRegistry
from oqlos.tools.hardware_diagnose.discovery import UsbDevice
from oqlos.tools.hardware_diagnose.doctor_common import LOCAL_FIRMWARE_HOSTS


def _doctor():
    """Lazy import so tests can monkeypatch names on the doctor facade module."""
    from oqlos.tools.hardware_diagnose import doctor

    return doctor


def usb_serial_only(devices: list[UsbDevice]) -> list[UsbDevice]:
    return [
        dev for dev in devices
        if dev.device.startswith(("/dev/ttyACM", "/dev/ttyUSB"))
    ]


def load_config_summary(config_path: str | Path | None) -> dict[str, Any]:
    try:
        resolved = resolve_oqlos_config_path(config_path)
        configs = PluginRegistry.load_configs_from_yaml(resolved)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "path": str(config_path or "")}

    plugins: dict[str, dict[str, Any]] = {}
    for plugin_id, config in configs.items():
        plugins[plugin_id] = {
            "enabled": config.enabled,
            "connection_type": config.connection_type,
            "connection_params": dict(config.connection_params),
            "timeout": config.timeout,
            "retry_count": config.retry_count,
        }

    return {
        "ok": True,
        "path": str(resolved),
        "plugins": plugins,
    }


def run_modbus_probe(probe: Callable[..., dict[str, Any]], probe_timeout: float) -> dict[str, Any]:
    capture = StringIO()
    try:
        with redirect_stdout(capture), redirect_stderr(capture):
            result = probe(timeout=probe_timeout)
    except Exception as exc:
        result = {
            "connected": False,
            "reason": str(exc),
            "modbus_device_responds": False,
        }

    diagnostic_output = [
        line.strip() for line in capture.getvalue().splitlines()
        if line.strip()
    ]
    if diagnostic_output:
        result["diagnostic_output"] = diagnostic_output[-10:]
    return result


def probe_modbus(probe_timeout: float) -> dict[str, Any]:
    return run_modbus_probe(_doctor().probe_waveshare_modbus, probe_timeout)


def probe_modbus_adc(probe_timeout: float) -> dict[str, Any]:
    return run_modbus_probe(_doctor().probe_waveshare_modbus_adc, probe_timeout)


def firmware_hostname(firmware_url: str) -> str:
    try:
        return (urlparse(firmware_url).hostname or "").lower()
    except Exception:
        return ""


def detect_hardware(
    firmware_url: str = "http://localhost:8202",
    *,
    config_path: str | Path | None = None,
    probe_timeout: float = 0.35,
    include_firmware: bool = True,
) -> dict[str, Any]:
    """Collect local and firmware-side hardware discovery signals."""
    doc = _doctor()
    usb_devices = doc.list_usb_serial_devices()
    usb_serial = usb_serial_only(usb_devices)

    modbus_probe = probe_modbus(probe_timeout)
    modbus_adc_probe = probe_modbus_adc(probe_timeout)

    result: dict[str, Any] = {
        "config": load_config_summary(config_path),
        "host": {
            "usb_devices": [dev.to_dict() for dev in usb_devices],
            "usb_serial_devices": [dev.to_dict() for dev in usb_serial],
            "serial_port_owners": doc._serial_port_owners(usb_serial),
            "i2c_buses": doc.list_i2c_buses(),
        },
        "probes": {
            "modbus": modbus_probe,
            "modbus_adc": modbus_adc_probe,
        },
    }

    if include_firmware:
        firmware_host = firmware_hostname(firmware_url)
        result["firmware"] = {
            "url": firmware_url,
            "host": firmware_host,
            "is_local": firmware_host in LOCAL_FIRMWARE_HOSTS,
            "health": doc.check_firmware_health(firmware_url),
            "identify": doc.check_firmware_identify(firmware_url),
        }

    return result
