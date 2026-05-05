"""USB/serial and I2C hardware discovery utilities."""

from __future__ import annotations

import glob
import subprocess
from dataclasses import dataclass
from typing import Optional

try:
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False


def _run_shell_command(cmd: list[str]) -> tuple[int, str, str]:
    """Run shell command and return (rc, stdout, stderr)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)


@dataclass
class UsbDevice:
    """USB device information."""
    device: str
    vid: Optional[int]
    pid: Optional[int]
    manufacturer: Optional[str]
    product: Optional[str]
    serial_number: Optional[str]
    description: str

    def to_dict(self) -> dict:
        return {
            "device": self.device,
            "vid": f"0x{self.vid:04X}" if self.vid else None,
            "pid": f"0x{self.pid:04X}" if self.pid else None,
            "manufacturer": self.manufacturer,
            "product": self.product,
            "serial": self.serial_number,
            "description": self.description,
        }


def list_usb_serial_devices() -> list[UsbDevice]:
    """Detect all USB-to-serial devices."""
    devices: list[UsbDevice] = []

    if HAS_SERIAL:
        for port in serial.tools.list_ports.comports():
            devices.append(UsbDevice(
                device=port.device,
                vid=port.vid,
                pid=port.pid,
                manufacturer=port.manufacturer,
                product=port.product,
                serial_number=port.serial_number,
                description=port.description or "Unknown",
            ))

    for device in sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")):
        if not any(d.device == device for d in devices):
            devices.append(UsbDevice(
                device=device,
                vid=None, pid=None, manufacturer=None,
                product=None, serial_number=None,
                description="USB Serial (from glob)",
            ))

    return devices


def list_i2c_buses() -> list[str]:
    """List available I2C buses."""
    return sorted(glob.glob("/dev/i2c-*"))


def detect_chips_on_i2c(bus: str = "/dev/i2c-1") -> list[dict]:
    """Detect chips on I2C bus using i2cdetect."""
    rc, stdout, _ = _run_shell_command(["i2cdetect", "-y", bus.replace("/dev/i2c-", "")])
    chips = []
    if rc == 0:
        for line in stdout.split("\n")[1:]:  # Skip header
            if line.strip() and not line.startswith("   "):
                parts = line.split()
                if len(parts) > 1:
                    row = parts[0].rstrip(":")
                    for i, addr in enumerate(parts[1:9], start=0):
                        if addr not in ["--", "UU"]:
                            chips.append({
                                "address": f"0x{row}{i:X}",
                                "raw": addr,
                                "bus": bus,
                            })
    return chips
