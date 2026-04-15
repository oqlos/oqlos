# firmware/api/hardware.py
"""Hardware health & control endpoints with live USB/serial/I2C probing."""

from __future__ import annotations

import asyncio
import fcntl
import glob
import logging
import os
import pathlib
from typing import Any

from fastapi import APIRouter
from oqlos.hardware.gateway import HardwareGateway
from oqlos.hardware.discovery import list_serial_ports, probe_waveshare_modbus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/hardware", tags=["hardware"])

_gateway: HardwareGateway | None = None

# Static hardware registry — describes adapters available in the system
_HARDWARE_REGISTRY: list[dict[str, Any]] = [
    {
        "id": "piadc",
        "name": "piADC (ADS1115)",
        "version": "1.0.2",
        "protocol": "I2C + REST",
        "description": "ADS1115 16-bit ADC — 4-channel analog input",
        "repo": "piadc",
        "channels": {"0": "NC sensor (mbar)", "1": "SC sensor (bar)", "2": "WC sensor (bar)", "3": "spare"},
    },
    {
        "id": "motor-tic249",
        "name": "Pololu Tic T249",
        "version": "0.1.13",
        "protocol": "USB + REST",
        "description": "Stepper motor controller — artificial lung pump",
        "repo": "rpi-motor-tic249",
        "capabilities": ["reciprocate", "homing", "limit-switches"],
    },
    {
        "id": "motor-dri0050",
        "name": "DFRobot DRI0050",
        "version": "1.0.0",
        "protocol": "MODBUS RTU (serial)",
        "description": "PWM motor & LED strip driver",
        "repo": "rpi-motor-DRI0050",
        "registers": ["PID", "VID", "Duty", "Frequency", "Enable"],
    },
    {
        "id": "modbus-io",
        "name": "Waveshare Modbus RTU IO 8CH",
        "version": "V2.00",
        "protocol": "Modbus RTU (RS485)",
        "description": "8DI + 8DO industrial I/O module — valve & signal control",
        "repo": "pimodbus",
        "digital_outputs": "DO1–DO8 (5–40V, open-drain, 500mA/ch)",
        "digital_inputs": "DI1–DI8 (5–36V, optocoupler isolated)",
        "interface": "RS485 via USB serial adapter",
        "default_config": "19200 baud, N-8-1, slave address 1",
        "wiki": "https://www.waveshare.com/wiki/Modbus_RTU_IO_8CH",
    },
]


# ---------------------------------------------------------------------------
# Low-level hardware probing (no external libs required)
# ---------------------------------------------------------------------------

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
            # Find the corresponding /dev/ttyUSB* device
            tty_devices = sorted(glob.glob("/dev/ttyUSB*"))
            return {
                "connected": True,
                "usb_product": dev.get("product", "CH340"),
                "usb_serial": dev.get("serial", ""),
                "serial_port": tty_devices[0] if tty_devices else "unknown",
            }
    return {"connected": False}


def _probe_i2c_ads1115() -> dict[str, Any]:
    """Probe I2C buses for ADS1115 at address 0x48."""
    I2C_SLAVE = 0x0703
    for bus_num in range(8):
        dev_path = f"/dev/i2c-{bus_num}"
        if not os.path.exists(dev_path):
            continue
        try:
            fd = os.open(dev_path, os.O_RDWR)
            try:
                fcntl.ioctl(fd, I2C_SLAVE, 0x48)
                os.read(fd, 1)
                os.close(fd)
                return {"connected": True, "bus": bus_num, "address": "0x48"}
            except OSError:
                os.close(fd)
        except PermissionError:
            return {"connected": False, "reason": f"permission denied on {dev_path}"}
        except OSError:
            pass
    return {"connected": False, "reason": "no I2C bus or no device at 0x48"}


def _probe_modbus_rtu() -> dict[str, Any]:
    """Detect the active Waveshare Modbus RTU serial port and line settings."""
    probe = probe_waveshare_modbus()
    if probe.get("connected") and not probe.get("modbus_device_responds", True):
        note = probe.get("note") or "USB serial adapter detected"
        probe["note"] = f"{note} (check power or RS485 wiring if this is unexpected)"
    return probe


def _probe_all_hardware() -> dict[str, Any]:
    """Run all hardware probes and return combined result."""
    usb_devices = _scan_usb_devices()
    return {
        "motor-tic249": _probe_tic249(usb_devices),
        "motor-dri0050": _probe_dri0050(usb_devices),
        "piadc": _probe_i2c_ads1115(),
        "modbus-io": _probe_modbus_rtu(),
    }


def _collect_hardware_diagnostics() -> dict[str, Any]:
    """Collect best-effort port and bus inventory for troubleshooting."""
    return {
        "usb_devices": _scan_usb_devices(),
        "serial_ports": list_serial_ports(),
        "i2c_buses": sorted(glob.glob("/dev/i2c-*")),
    }


def set_hardware_gateway(gw: HardwareGateway) -> None:
    global _gateway
    _gateway = gw


def _gw() -> HardwareGateway:
    if _gateway is None:
        raise RuntimeError("HardwareGateway not initialised")
    return _gateway


@router.get("/health")
async def hardware_health():
    """Return connectivity status for all hardware services."""
    return await _gw().health()


@router.get("/identify")
async def hardware_identify():
    """Return full hardware identification: registry + live probe results."""
    health_task = asyncio.create_task(_gw().health())
    probes_task = asyncio.to_thread(_probe_all_hardware)
    diagnostics_task = asyncio.to_thread(_collect_hardware_diagnostics)

    health, probes, diagnostics = await asyncio.gather(health_task, probes_task, diagnostics_task)

    adapters = []
    for hw in _HARDWARE_REGISTRY:
        hw_id = hw["id"]
        probe = probes.get(hw_id, {})
        entry = {**hw, "status": "offline", "probe": probe}

        if probe.get("connected"):
            # For modbus-io: adapter present but module may not respond
            if hw_id == "modbus-io" and not probe.get("modbus_device_responds", True):
                entry["status"] = "adapter-only"
            else:
                entry["status"] = "ok"
        elif probe.get("reason"):
            entry["status"] = "no-access"
        else:
            entry["status"] = "offline"

        adapters.append(entry)

    mode = health.get("mode", "mock")
    connected_count = sum(1 for a in adapters if a["status"] == "ok")
    return {
        "mode": mode,
        "detected": connected_count,
        "total": len(adapters),
        "adapters": adapters,
        "diagnostics": {
            "health": health,
            **diagnostics,
        },
    }


@router.post("/valve/{valve_id}")
async def set_valve(valve_id: str, value: bool):
    """Directly set a valve (for manual testing)."""
    ok = await _gw().set_valve(valve_id, value)
    return {"valve_id": valve_id, "value": value, "ok": ok}


@router.post("/pump")
async def set_pump(power_pct: float = 0.0):
    """Directly set pump power % (for manual testing)."""
    ok = await _gw().set_pump(power_pct)
    return {"power_pct": power_pct, "ok": ok}


@router.get("/sensor/{sensor_id}")
async def read_sensor(sensor_id: str):
    """Read a sensor value directly from hardware."""
    value = await _gw().read_sensor(sensor_id)
    return {"sensor_id": sensor_id, "value": value}


@router.post("/lung")
async def set_lung(steps: int = 500, speed: int = 100000, cycles: int = 5, pause: float = 0.5):
    """Start artificial lung reciprocating motion (tic249 stepper)."""
    ok = await _gw().set_lung(steps=steps, speed=speed, cycles=cycles, pause=pause)
    return {"steps": steps, "speed": speed, "cycles": cycles, "pause": pause, "ok": ok}


@router.post("/lung/stop")
async def stop_lung():
    """Emergency stop the artificial lung motor."""
    ok = await _gw().stop_lung()
    return {"ok": ok, "status": "stopped"}
