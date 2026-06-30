"""USB, I2C, and Modbus RTU live device probe helpers."""

from __future__ import annotations

import fcntl
import glob
import os
import pathlib
from typing import Any

from oqlos.api import hardware_platform as platform
from oqlos.config import get_settings
from oqlos.hardware.discovery import probe_waveshare_modbus, probe_waveshare_modbus_adc

_settings = get_settings()


def _local_ads1115_probe_allowed() -> bool:
    selection = platform._selected_piadc_platform()
    if selection in {"desktop", "external-rpi"}:
        return False
    if selection in {"raspberry-pi", "generic-linux"}:
        return True
    return os.getenv("ADS1115_ALLOW_NON_RPI", "false").lower() == "true" or platform._is_raspberry_pi_host()


def _scan_usb_devices() -> list[dict[str, str]]:
    """Scan /sys/bus/usb/devices for connected USB devices (vendor:product)."""
    devices: list[dict[str, str]] = []
    usb_base = pathlib.Path("/sys/bus/usb/devices")
    if not usb_base.exists():
        return devices
    for dev_dir in usb_base.iterdir():
        vid_path = dev_dir / "idVendor"
        pid_path = dev_dir / "idProduct"
        if vid_path.exists() and pid_path.exists():
            try:
                vid = vid_path.read_text().strip()
                pid = pid_path.read_text().strip()
                manufacturer = ""
                product = ""
                serial = ""
                mfg_path = dev_dir / "manufacturer"
                prod_path = dev_dir / "product"
                ser_path = dev_dir / "serial"
                if mfg_path.exists():
                    manufacturer = mfg_path.read_text().strip()
                if prod_path.exists():
                    product = prod_path.read_text().strip()
                if ser_path.exists():
                    serial = ser_path.read_text().strip()
                devices.append({
                    "vendor_id": vid,
                    "product_id": pid,
                    "manufacturer": manufacturer,
                    "product": product,
                    "serial": serial,
                    "path": str(dev_dir),
                })
            except OSError:
                pass
    return devices


def _probe_tic249(usb_devices: list[dict[str, str]]) -> dict[str, Any]:
    """Detect Pololu Tic T249 (vendor 1ffb, product 00c9) via USB sysfs."""
    for dev in usb_devices:
        if dev["vendor_id"] == "1ffb" and dev["product_id"] == "00c9":
            return {
                "connected": True,
                "usb_product": dev.get("product", "Tic T249"),
                "usb_serial": dev.get("serial", ""),
                "usb_path": dev.get("path", ""),
            }
    return {"connected": False}


def _probe_dri0050(usb_devices: list[dict[str, str]]) -> dict[str, Any]:
    """Detect DRI0050 — CH340/CH341 USB-serial converter (vendor 1a86, product 7523)."""
    for dev in usb_devices:
        if dev["vendor_id"] == "1a86" and dev["product_id"] in ("7523", "55d3"):
            tty_devices = sorted(glob.glob("/dev/ttyUSB*"))
            return {
                "connected": True,
                "usb_product": dev.get("product", "CH340"),
                "usb_serial": dev.get("serial", ""),
                "serial_port": tty_devices[0] if tty_devices else "unknown",
            }
    return {"connected": False}


def _probe_i2c_ads1115() -> dict[str, Any]:
    """Probe configured I2C bus(es) for ADS1115."""
    piadc_url = os.getenv("OQLOS_PIADC_URL") or os.getenv("PIADC_URL") or "http://localhost:8204"
    if not _local_ads1115_probe_allowed():
        return {
            "connected": False,
            "skipped": True,
            "reason": (
                "local ADS1115 HAT probe skipped: this host does not look like Raspberry Pi "
                f"(machine={platform.machine() or 'unknown'}). Run piADC on the Raspberry Pi "
                "that owns the HAT and point OqlOS to it with PIADC_URL/OQLOS_PIADC_URL."
            ),
            "remote_url": piadc_url,
        }

    I2C_SLAVE = 0x0703
    address_raw = os.getenv("ADS1115_I2C_ADDRESS", "0x48")
    try:
        address = int(address_raw, 0)
    except ValueError:
        address = 0x48

    bus_raw = os.getenv("ADS1115_I2C_BUS")
    if bus_raw not in (None, ""):
        try:
            bus_numbers = [int(bus_raw)]
        except ValueError:
            bus_numbers = []
    else:
        bus_numbers = list(range(8))

    reasons: list[str] = []
    for bus_num in bus_numbers:
        dev_path = f"/dev/i2c-{bus_num}"
        if not os.path.exists(dev_path):
            reasons.append(f"{dev_path} does not exist")
            continue
        try:
            fd = os.open(dev_path, os.O_RDWR)
            try:
                fcntl.ioctl(fd, I2C_SLAVE, address)
                os.read(fd, 1)
                os.close(fd)
                return {"connected": True, "bus": bus_num, "address": hex(address)}
            except OSError as exc:
                os.close(fd)
                reasons.append(f"{dev_path} {hex(address)} probe failed: {exc}")
        except PermissionError:
            reasons.append(f"permission denied on {dev_path}")
        except OSError as exc:
            reasons.append(f"{dev_path} open failed: {exc}")

    reason = "; ".join(reasons) if reasons else f"no I2C bus or no device at {hex(address)}"
    return {"connected": False, "reason": reason, "address": hex(address), "buses": bus_numbers}


def _probe_waveshare_rtu(
    probe_fn: Any,
    *,
    preferred_port: str,
    preferred_baud: int,
    preferred_parity: str,
    preferred_device_id: int,
    wiring_hint: str,
) -> dict[str, Any]:
    probe = probe_fn(
        preferred_port=preferred_port,
        preferred_baud=preferred_baud,
        preferred_parity=preferred_parity,
        preferred_device_id=preferred_device_id,
    )
    if probe.get("connected") and not probe.get("modbus_device_responds", True):
        note = probe.get("note") or "USB serial adapter detected"
        probe["note"] = f"{note} ({wiring_hint})"
    return probe


def _probe_configured_waveshare_rtu(role: str) -> dict[str, Any]:
    specs = {
        "modbus-io": {
            "probe_fn": probe_waveshare_modbus,
            "preferred_port": _settings.modbus_serial_port,
            "preferred_baud": _settings.modbus_baud,
            "preferred_parity": _settings.modbus_parity,
            "preferred_device_id": _settings.modbus_device_id,
            "wiring_hint": "check power or RS485 wiring if this is unexpected",
        },
        "modbus-adc": {
            "probe_fn": probe_waveshare_modbus_adc,
            "preferred_port": _settings.modbus_adc_serial_port,
            "preferred_baud": _settings.modbus_adc_baud,
            "preferred_parity": _settings.modbus_adc_parity,
            "preferred_device_id": _settings.modbus_adc_device_id,
            "wiring_hint": "check power, address, baudrate, or RS485 wiring if this is unexpected",
        },
    }
    return _probe_waveshare_rtu(**specs[role])
