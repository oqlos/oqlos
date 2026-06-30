# firmware/api/hardware.py
"""Hardware health & control endpoints with live USB/serial/I2C probing."""

from __future__ import annotations

import asyncio
import fcntl
import glob
import inspect
import logging
import os
import pathlib
import platform
import subprocess
import sys
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse
from oqlos.config import get_settings
from oqlos.hardware.discovery import list_serial_ports, probe_waveshare_modbus, probe_waveshare_modbus_adc
from oqlos.hardware.artificial_lung import execute_command as execute_artificial_lung_command
from oqlos.hardware.artificial_lung import get_peripheral_status as get_artificial_lung_status
from oqlos.hardware.hui_actions import (
    list_hui_actions,
    shutdown_all_hui_hardware,
    start_hui_artificial_lung,
    start_hui_hold,
    stop_hui_artificial_lung,
    stop_hui_hold,
)
from oqlos.hardware.identify_enrichment import enrich_identify_payload
from oqlos.hardware.rtc_probe import build_rtc_peripheral_status, run_rtc_command
from oqlos.hardware.tic249_units import TIC249_DEFAULT_TARGET_VELOCITY

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/hardware", tags=["hardware"])

_gateway: Any | None = None
_settings = get_settings()

# Static hardware registry — describes adapters available in the system
_HARDWARE_REGISTRY: list[dict[str, Any]] = [
    {
        "id": "modbus-adc",
        "name": "Waveshare Modbus RTU Analog Input 8CH",
        "version": "1.0.0",
        "protocol": "Modbus RTU (RS485)",
        "description": "8-channel analog input module - pressure sensors",
        "repo": "waveshare-modbus-rtu-analog-input-8ch",
        "channels": {
            "0": "AI01 NC sensor",
            "1": "AI02 SC sensor",
            "2": "AI03 WC sensor",
            "3": "AI04 spare",
            "4": "AI05 spare",
            "5": "AI06 spare",
            "6": "AI07 spare",
            "7": "AI08 spare",
        },
        "interface": "RS485 via USB serial adapter",
        "default_config": "9600 baud, N-8-1, slave address 1, input registers 0x0000-0x0007",
        "wiki": "https://www.waveshare.com/wiki/Modbus_RTU_Analog_Input_8CH",
    },
    {
        "id": "motor-tic249",
        "name": "Pololu Tic T249",
        "version": "0.1.13",
        "protocol": "USB + REST",
        "description": "Stepper motor controller - artificial lung pump",
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
        "description": "8DI + 8DO industrial I/O module - valve & signal control",
        "repo": "pimodbus",
        "digital_outputs": "DO1-DO8 (5-40V, open-drain, 500mA/ch)",
        "digital_inputs": "DI1-DI8 (5-36V, optocoupler isolated)",
        "interface": "RS485 via USB serial adapter",
        "default_config": "9600 baud, N-8-1, slave address 1",
        "wiki": "https://www.waveshare.com/wiki/Modbus_RTU_IO_8CH",
    },
]


# ---------------------------------------------------------------------------
# Low-level hardware probing (no external libs required)
# ---------------------------------------------------------------------------


def _read_text_file(path: str) -> str:
    try:
        return pathlib.Path(path).read_text(encoding="utf-8", errors="ignore").strip("\x00\n ")
    except OSError:
        return ""


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
    return any(marker in cgroup for marker in ("docker", "containerd", "kubepods", "podman"))


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
    value = os.getenv("PIADC_PLATFORM") or os.getenv("ADS1115_PLATFORM") or _selected_hardware_platform()
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
    modbus_ports = _modbus_runtime_serial_ports()
    modbus_io_serial = modbus_ports["io_serial_port"]
    modbus_adc_serial = modbus_ports["adc_serial_port"]

    return {
        "selected": _selected_hardware_platform(),
        "piadc_selected": piadc_selected,
        "modbus_adc_selected": "modbus-rtu",
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
        "analog_input_driver_role": "modbus-rtu",
        "modbus_topology": modbus_ports["topology"],
        "modbus_topology_mode": modbus_ports["topology_mode"],
        "modbus_bus_serial_port": modbus_ports.get("shared_serial_port") or (
            modbus_io_serial if modbus_io_serial == modbus_adc_serial else ""
        ),
        "modbus_io_serial_port": modbus_io_serial,
        "modbus_adc_driver_role": "modbus-rtu",
        "modbus_adc_serial_port": modbus_adc_serial,
        "modbus_adc_local_probe_allowed": True,
        "piadc_driver_role": "replaced-by-modbus-adc",
        "piadc_local_probe_allowed": False,
        "i2c_buses": sorted(glob.glob("/dev/i2c-*")),
        "serial_ports": [port.get("device") for port in list_serial_ports()],
    }


def _local_ads1115_probe_allowed() -> bool:
    selection = _selected_piadc_platform()
    if selection in {"desktop", "external-rpi"}:
        return False
    if selection in {"raspberry-pi", "generic-linux"}:
        return True
    return os.getenv("ADS1115_ALLOW_NON_RPI", "false").lower() == "true" or _is_raspberry_pi_host()


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


def _probe_all_hardware(ids: set[str] | None = None) -> dict[str, Any]:
    """Run selected hardware probes and return combined result."""
    selected = ids or {hw["id"] for hw in _HARDWARE_REGISTRY}
    usb_devices: list[dict[str, str]] | None = None
    results: dict[str, Any] = {}

    if "motor-tic249" in selected or "motor-dri0050" in selected:
        usb_devices = _scan_usb_devices()
    if "motor-tic249" in selected:
        results["motor-tic249"] = _probe_tic249(usb_devices or [])
    if "motor-dri0050" in selected:
        results["motor-dri0050"] = _probe_dri0050(usb_devices or [])
    if "modbus-adc" in selected:
        results["modbus-adc"] = _probe_configured_waveshare_rtu("modbus-adc")
    if "modbus-io" in selected:
        results["modbus-io"] = _probe_configured_waveshare_rtu("modbus-io")
    return results


def _collect_hardware_diagnostics() -> dict[str, Any]:
    """Collect best-effort port and bus inventory for troubleshooting."""
    return {
        "platform": _detect_runtime_platform(),
        "usb_devices": _scan_usb_devices(),
        "serial_ports": list_serial_ports(),
        "i2c_buses": sorted(glob.glob("/dev/i2c-*")),
        "modbus_preflight": _modbus_preflight_report(),
    }


def _is_plugin_compatible(health_entry: Any) -> bool:
    """Return True when plugin health confirms adapter is reachable and compatible."""
    return isinstance(health_entry, dict) and bool(health_entry.get("compatible"))


def _needs_live_scan(health: dict[str, Any]) -> bool:
    """Run expensive live scan only when at least one registered adapter is not compatible."""
    for hw in _HARDWARE_REGISTRY:
        if not _is_plugin_compatible(health.get(hw["id"])):
            return True
    return False


def _unhealthy_plugin_ids(health: dict[str, Any]) -> set[str]:
    """Return adapter ids whose plugin health is not compatible."""
    return {
        hw["id"]
        for hw in _HARDWARE_REGISTRY
        if not _is_plugin_compatible(health.get(hw["id"]))
    }


def _modbus_health_is_no_response(health_entry: dict[str, Any]) -> bool:
    """Return True when the serial adapter is open but the Modbus device is silent."""
    message = str(health_entry.get("message") or "")
    return (
        "read_coils" in message
        or "read_input_registers" in message
        or "No response" in message
        or "timed out" in message
    )


def _probe_selected_hardware(ids: set[str]) -> dict[str, Any]:
    """Run selected probes while staying compatible with older monkeypatched tests."""
    if len(inspect.signature(_probe_all_hardware).parameters) == 0:
        return _probe_all_hardware()  # type: ignore[call-arg]
    return _probe_all_hardware(ids)


def _modbus_preflight_report() -> dict[str, Any]:
    gateway = _gateway
    if gateway is not None and hasattr(gateway, "modbus_preflight_report"):
        try:
            report = gateway.modbus_preflight_report()
            if isinstance(report, dict):
                return report
        except Exception as exc:
            return {
                "ok": False,
                "topology": "unknown",
                "modules": [],
                "issues": [
                    {
                        "severity": "error",
                        "code": "modbus_preflight_exception",
                        "message": str(exc),
                        "modules": ["modbus-io", "modbus-adc"],
                        "repair": {},
                    }
                ],
                "recommended": {},
            }
    return {"ok": True, "topology": "unknown", "modules": [], "issues": [], "recommended": {}}


def _modbus_repair_guidance(health: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        from pimodbus.repair import build_runtime_repair_guidance
    except ImportError as exc:
        return {
            "available": False,
            "error": f"pimodbus repair module is not available: {exc}",
        }

    return build_runtime_repair_guidance(
        serial_port=_settings.modbus_serial_port,
        baudrate=_settings.modbus_baud,
        parity=_settings.modbus_parity,
        io_device_id=_settings.modbus_device_id,
        adc_device_id=_settings.modbus_adc_device_id,
        health=health or {},
    )


def _parse_csv_ints(raw: str | None, default: list[int]) -> list[int]:
    values: list[int] = []
    for part in str(raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            value = int(part)
        except ValueError:
            continue
        if value > 0 and value not in values:
            values.append(value)
    return values or list(default)


def _modbus_io_device_ids() -> list[int]:
    configured = os.getenv("OQLOS_MODBUS_IO_DEVICE_IDS") or os.getenv("MODBUS_IO_DEVICE_IDS")
    return _parse_csv_ints(configured, [_settings.modbus_device_id])


def _modbus_topology_mode() -> str:
    """How RS485 wiring is interpreted: auto-detect, one adapter, or point-to-point."""
    raw = (os.getenv("OQLOS_MODBUS_TOPOLOGY") or os.getenv("MODBUS_TOPOLOGY") or "auto").strip().lower()
    if raw in {"shared", "shared-bus", "one-bus", "single-adapter", "single"}:
        return "shared-bus"
    if raw in {"separate", "separate-adapters", "p2p", "point-to-point", "dual-adapter", "dual"}:
        return "separate-adapters"
    return "auto"


def _apply_modbus_topology(
    mode: str, bus_port: str, io_port: str, adc_port: str
) -> tuple[str, str, str]:
    """Return (io_port, adc_port, topology) after applying topology-mode rules."""
    if mode == "shared-bus":
        shared = bus_port or io_port or adc_port
        return shared, shared, "shared-bus"
    if mode == "separate-adapters":
        adc_port = adc_port or io_port
        return io_port, adc_port, "separate-adapters"
    if bus_port:
        return bus_port, bus_port, "shared-bus"
    adc_port = adc_port or io_port
    topology = (
        "separate-adapters"
        if (io_port and adc_port and io_port != adc_port)
        else "shared-bus"
    )
    return io_port, adc_port, topology


def _modbus_runtime_serial_ports() -> dict[str, Any]:
    """Resolve IO vs ADC serial ports for shared-bus or separate USB-RS485 adapters."""
    bus_port = (
        os.getenv("OQLOS_MODBUS_BUS_SERIAL_PORT")
        or os.getenv("MODBUS_BUS_SERIAL_PORT")
        or os.getenv("OQLOS_MODBUS_SHARED_SERIAL_PORT")
        or os.getenv("MODBUS_SHARED_SERIAL_PORT")
        or ""
    ).strip()
    io_port = (
        os.getenv("OQLOS_MODBUS_SERIAL_PORT")
        or os.getenv("MODBUS_SERIAL_PORT")
        or str(_settings.modbus_serial_port or "")
    ).strip()
    adc_port = (
        os.getenv("OQLOS_MODBUS_ADC_SERIAL_PORT")
        or os.getenv("MODBUS_ADC_SERIAL_PORT")
        or str(_settings.modbus_adc_serial_port or "")
    ).strip()
    mode = _modbus_topology_mode()

    io_port, adc_port, topology = _apply_modbus_topology(mode, bus_port, io_port, adc_port)

    return {
        "io_serial_port": io_port,
        "adc_serial_port": adc_port,
        "shared_serial_port": io_port if topology == "shared-bus" else "",
        "topology": topology,
        "topology_mode": mode,
    }


def _diagnose_shared_bus_matrix(
    *,
    serial_port: str,
    target_baudrate: int,
    target_parity: str,
    io_device_id: int,
    adc_device_id: int,
    device_ids: list[int],
    required_roles: list[str] | None = None,
    timeout_fast: float = 0.5,
    timeout_full: float = 0.35,
):
    from pimodbus.repair import diagnose_shared_bus

    baud_sequence = [4800, 9600, 19200, 38400, 57600, 115200]
    target_report = diagnose_shared_bus(
        serial_port=serial_port,
        target_baudrate=target_baudrate,
        target_parity=target_parity,
        io_device_id=io_device_id,
        adc_device_id=adc_device_id,
        baudrates=[int(target_baudrate)],
        parities=[str(target_parity).upper()],
        device_ids=device_ids,
        timeout=timeout_fast,
        scan_all_ports=True,
        required_roles=required_roles,
    )
    if target_report.ok:
        return target_report
    return diagnose_shared_bus(
        serial_port=serial_port,
        target_baudrate=target_baudrate,
        target_parity=target_parity,
        io_device_id=io_device_id,
        adc_device_id=adc_device_id,
        baudrates=baud_sequence,
        parities=["N", "E", "O"],
        device_ids=device_ids,
        timeout=timeout_full,
        scan_all_ports=True,
        required_roles=required_roles,
    )


def _merge_unique_text_list(existing: list[str], new_items: "list[Any]") -> None:
    """Append string items from new_items to existing, skipping duplicates."""
    for item in new_items or []:
        text = str(item)
        if text and text not in existing:
            existing.append(text)


def _merge_waveshare_scan_dicts(*reports: dict[str, Any]) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    recommendations: list[str] = []
    actions: list[dict[str, Any]] = []
    targets: list[dict[str, Any]] = []
    for report in reports:
        if not isinstance(report, dict):
            continue
        hits.extend(list(report.get("hits") or []))
        issues.extend(list(report.get("issues") or []))
        _merge_unique_text_list(recommendations, report.get("recommendations"))
        actions.extend(list(report.get("actions") or []))
        target = report.get("target")
        if isinstance(target, dict):
            targets.append(target)
    merged_target = targets[0] if len(targets) == 1 else {"buses": targets}
    return {
        "ok": False,
        "safe_to_auto_apply": all(bool(report.get("safe_to_auto_apply")) for report in reports if isinstance(report, dict)),
        "target": merged_target,
        "hits": hits,
        "issues": issues,
        "actions": actions,
        "recommendations": recommendations,
        "probe_summary": reports[-1].get("probe_summary") if reports else {},
    }


def _read_output_control_modes(
    serial_port: str,
    baudrate: int,
    parity: str,
    device_id: int,
    timeout: float = 1.5,
) -> dict[str, Any]:
    try:
        from pymodbus.client import ModbusSerialClient  # type: ignore
    except Exception as exc:
        return {"ok": False, "error": f"pymodbus unavailable: {exc}"}

    client = ModbusSerialClient(
        port=serial_port,
        baudrate=int(baudrate),
        parity=str(parity),
        stopbits=1,
        bytesize=8,
        timeout=float(timeout),
    )
    try:
        if not client.connect():
            return {"ok": False, "error": f"Cannot open serial port {serial_port}"}
        result = client.read_holding_registers(address=0x1000, count=8, device_id=int(device_id))
        if not result or result.isError():
            return {"ok": False, "error": "Failed to read holding registers 0x1000..0x1007"}
        registers = list(getattr(result, "registers", []) or [])
        return {"ok": True, "registers": registers}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        try:
            client.close()
        except Exception:
            pass


def _modbus_plugins_healthy(health: dict[str, Any] | None) -> bool:
    """True when both Modbus plugins report compatible (ports held by firmware)."""
    if not isinstance(health, dict):
        return False
    return _is_plugin_compatible(health.get("modbus-io")) and _is_plugin_compatible(
        health.get("modbus-adc")
    )


def _modbus_health_serial_stale(health: dict[str, Any] | None) -> bool:
    """True when Modbus plugins hit EIO — typical after USB re-enumeration (tty remap)."""
    if not isinstance(health, dict):
        return False
    for plugin_id in ("modbus-io", "modbus-adc"):
        entry = health.get(plugin_id)
        if not isinstance(entry, dict):
            continue
        message = str(entry.get("message") or "").lower()
        if "errno 5" in message or "input/output error" in message:
            return True
    return False


def _build_waveshare_serial_stale_report(
    health: dict[str, Any],
    *,
    ports: dict[str, Any],
    io_ids: list[int],
    adc_id: int,
    baud_sequence: list[int],
) -> dict[str, Any]:
    """Do not run matrix scan on stale handles — restart OqlOS to reopen tty/by-id."""
    io_port = ports["io_serial_port"] or str(_settings.modbus_serial_port)
    adc_port = ports["adc_serial_port"] or io_port
    skip_reason = "Modbus serial handle stale (USB re-enumeration); restart OqlOS"
    per_slave: dict[str, Any] = {}
    for io_id in io_ids:
        per_slave[f"modbus-io-{io_id}"] = {
            "ok": False,
            "status": "serial-stale",
            "device_id": io_id,
            "source": "plugin-health",
            "message": str((health.get("modbus-io") or {}).get("message") or skip_reason),
        }
    per_slave[f"modbus-adc-{adc_id}"] = {
        "ok": False,
        "status": "serial-stale",
        "device_id": adc_id,
        "source": "plugin-health",
        "message": str((health.get("modbus-adc") or {}).get("message") or skip_reason),
    }
    return {
        "ok": False,
        "serial_handles_stale": True,
        "baud_sequence": baud_sequence,
        "io_device_ids": io_ids,
        "adc_device_id": adc_id,
        "topology": ports["topology"],
        "io_serial_port": io_port,
        "adc_serial_port": adc_port,
        "waveshare_scan": {
            "ok": False,
            "scan_skipped": True,
            "scan_skip_reason": skip_reason,
            "issues": [
                {
                    "severity": "error",
                    "code": "serial_handle_stale",
                    "message": skip_reason,
                    "roles": ["modbus-io", "modbus-adc"],
                }
            ],
            "recommendations": [
                "USB adapters are visible but OqlOS still holds old tty handles (e.g. ttyACM1→ttyACM2).",
                "Run: cd c2004 && make hardware-oqlos-only",
                "Or: systemctl --user restart oqlos-hardware-api.service",
                "Then refresh hardware-status before running valve/ADC tests.",
            ],
            "topology": ports["topology"],
            "ports_scanned": [
                {"role": "modbus-io", "serial_port": io_port},
                {"role": "modbus-adc", "serial_port": adc_port},
            ],
        },
        "per_slave": per_slave,
    }


def _build_waveshare_from_plugin_health(
    health: dict[str, Any],
    *,
    ports: dict[str, Any],
    io_ids: list[int],
    adc_id: int,
    target_baud: int,
    target_parity: str,
    baud_sequence: list[int],
) -> dict[str, Any]:
    """Skip RS485 matrix scan when OqlOS plugins already own the serial ports."""
    io_port = ports["io_serial_port"] or str(_settings.modbus_serial_port)
    adc_port = ports["adc_serial_port"] or io_port
    separate = ports["topology"] == "separate-adapters"
    skip_reason = "plugin owns Modbus serial port; inline scan skipped"
    per_slave: dict[str, Any] = {}
    hits: list[dict[str, Any]] = []

    for io_id in io_ids:
        key = f"modbus-io-{io_id}"
        per_slave[key] = {
            "ok": True,
            "status": "connected",
            "device_id": io_id,
            "source": "plugin-health",
            "message": str((health.get("modbus-io") or {}).get("message") or "Modbus RTU is healthy"),
            "detected": {
                "serial_port": io_port,
                "baudrate": target_baud,
                "parity": target_parity,
            },
            "output_modes_registers_0x1000_0x1007": {
                "ok": None,
                "skipped": True,
                "reason": skip_reason,
            },
        }
        hits.append(
            {
                "role": "modbus-io",
                "serial_port": io_port,
                "baudrate": target_baud,
                "parity": target_parity,
                "device_id": io_id,
                "function": "read_coils",
                "source": "plugin-health",
            }
        )

    adc_key = f"modbus-adc-{adc_id}"
    per_slave[adc_key] = {
        "ok": True,
        "status": "connected",
        "device_id": adc_id,
        "source": "plugin-health",
        "message": str((health.get("modbus-adc") or {}).get("message") or "Modbus ADC is healthy"),
        "detected": {
            "serial_port": adc_port,
            "baudrate": target_baud,
            "parity": target_parity,
        },
    }
    hits.append(
        {
            "role": "modbus-adc",
            "serial_port": adc_port,
            "baudrate": target_baud,
            "parity": target_parity,
            "device_id": adc_id,
            "function": "read_input_registers",
            "source": "plugin-health",
        }
    )

    scan_target: dict[str, Any]
    if separate:
        scan_target = {
            "buses": [
                {
                    "serial_port": io_port,
                    "baudrate": target_baud,
                    "parity": target_parity,
                    "io_device_id": int(_settings.modbus_device_id),
                    "adc_device_id": adc_id,
                },
                {
                    "serial_port": adc_port,
                    "baudrate": target_baud,
                    "parity": target_parity,
                    "io_device_id": int(_settings.modbus_device_id),
                    "adc_device_id": adc_id,
                },
            ]
        }
        ports_scanned = [
            {"role": "modbus-io", "serial_port": io_port},
            {"role": "modbus-adc", "serial_port": adc_port},
        ]
    else:
        scan_target = {
            "serial_port": io_port,
            "baudrate": target_baud,
            "parity": target_parity,
            "io_device_id": int(_settings.modbus_device_id),
            "adc_device_id": adc_id,
        }
        ports_scanned = []

    return {
        "ok": True,
        "baud_sequence": baud_sequence,
        "io_device_ids": io_ids,
        "adc_device_id": adc_id,
        "topology": ports["topology"],
        "io_serial_port": io_port,
        "adc_serial_port": adc_port,
        "waveshare_scan": {
            "ok": True,
            "safe_to_auto_apply": False,
            "scan_skipped": True,
            "scan_skip_reason": skip_reason,
            "target": scan_target,
            "hits": hits,
            "issues": [],
            "actions": [],
            "recommendations": [
                "Modbus IO/ADC are healthy via OqlOS plugins. For UART/register deep-check, "
                "use hardware restart wizard (exclusive scan) or stop OqlOS before pimodbus diagnose.",
            ],
            "topology": ports["topology"],
            "ports_scanned": ports_scanned,
        },
        "per_slave": per_slave,
        "plugin_health_deferred": True,
    }


def _probe_waveshare_separate(
    io_port: str,
    adc_port: str,
    target_baud: int,
    target_parity: str,
    io_device_id: int,
    io_ids: list,
    adc_id: int,
) -> tuple[dict, bool]:
    """Probe two separate RS485 adapters; return (merged_report_dict, ok)."""
    io_report = _diagnose_shared_bus_matrix(
        serial_port=io_port,
        target_baudrate=target_baud,
        target_parity=target_parity,
        io_device_id=io_device_id,
        adc_device_id=adc_id,
        device_ids=io_ids,
        required_roles=["modbus-io"],
    )
    adc_report = _diagnose_shared_bus_matrix(
        serial_port=adc_port,
        target_baudrate=target_baud,
        target_parity=target_parity,
        io_device_id=io_device_id,
        adc_device_id=adc_id,
        device_ids=[adc_id],
        required_roles=["modbus-adc"],
    )
    report_ok = bool(io_report.ok and adc_report.ok)
    report_dict = _merge_waveshare_scan_dicts(io_report.to_dict(), adc_report.to_dict())
    report_dict["ok"] = report_ok
    report_dict["topology"] = "separate-adapters"
    report_dict["ports_scanned"] = [
        {"role": "modbus-io", "serial_port": io_port},
        {"role": "modbus-adc", "serial_port": adc_port},
    ]
    return report_dict, report_ok


def _probe_waveshare_shared_bus(
    io_port: str,
    target_baud: int,
    target_parity: str,
    io_device_id: int,
    adc_id: int,
    target_ids: list,
) -> tuple[dict, bool]:
    """Probe a single shared RS485 bus; return (report_dict, ok)."""
    report = _diagnose_shared_bus_matrix(
        serial_port=io_port,
        target_baudrate=target_baud,
        target_parity=target_parity,
        io_device_id=io_device_id,
        adc_device_id=adc_id,
        device_ids=target_ids,
    )
    report_dict = report.to_dict()
    report_dict["topology"] = "shared-bus"
    return report_dict, bool(report.ok)


def _read_waveshare_io_slave_config(
    io_id: int,
    io_hits: list,
    io_port: str,
    target_baud: int,
    target_parity: str,
) -> dict:
    """Read device config and control modes for one modbus-io slave; return per-slave dict."""
    from pimodbus.config import RtuBusSettings
    from pimodbus.provisioning import read_device_config
    hit = next((entry for entry in io_hits if int(entry.get("device_id", -1)) == io_id), None)
    if not hit:
        return {
            "ok": False,
            "status": "no-response",
            "device_id": io_id,
            "message": "No Modbus RTU response for this slave id in Waveshare scan matrix",
        }
    settings = RtuBusSettings(
        serial_port=str(hit.get("serial_port") or io_port),
        baudrate=int(hit.get("baudrate") or target_baud),
        parity=str(hit.get("parity") or target_parity),
        timeout=1.5,
    )
    try:
        config = read_device_config(settings, device_id=io_id).to_dict()
    except Exception as exc:
        return {
            "ok": False,
            "status": "read-error",
            "device_id": io_id,
            "message": str(exc),
        }
    control_modes = _read_output_control_modes(
        settings.serial_port,
        settings.baudrate,
        settings.parity,
        io_id,
        timeout=settings.timeout,
    )
    return {
        "ok": True,
        "status": "ok",
        "device_id": io_id,
        "detected": {
            "serial_port": settings.serial_port,
            "baudrate": settings.baudrate,
            "parity": settings.parity,
            "function": hit.get("function"),
        },
        "slave_address_register_0x4000": config.get("device_id"),
        "uart_register_0x2000": {
            "baudrate": config.get("baudrate"),
            "parity": config.get("parity"),
        },
        "output_modes_registers_0x1000_0x1007": control_modes,
    }


def _read_waveshare_adc_slave_config(
    adc_id: int,
    adc_hits: list,
    adc_port: str,
    target_baud: int,
    target_parity: str,
) -> dict:
    """Read device config for the modbus-adc slave; return per-slave dict."""
    from pimodbus.config import RtuBusSettings
    from pimodbus.provisioning import read_device_config
    adc_hit = next((entry for entry in adc_hits if int(entry.get("device_id", -1)) == adc_id), None)
    if not adc_hit:
        return {
            "ok": False,
            "status": "no-response",
            "device_id": adc_id,
            "message": "No Modbus RTU response for ADC slave id in Waveshare scan matrix",
        }
    settings = RtuBusSettings(
        serial_port=str(adc_hit.get("serial_port") or adc_port),
        baudrate=int(adc_hit.get("baudrate") or target_baud),
        parity=str(adc_hit.get("parity") or target_parity),
        timeout=1.5,
    )
    try:
        config = read_device_config(settings, device_id=adc_id).to_dict()
    except Exception as exc:
        return {
            "ok": False,
            "status": "read-error",
            "device_id": adc_id,
            "message": str(exc),
        }
    return {
        "ok": True,
        "status": "ok",
        "device_id": adc_id,
        "detected": {
            "serial_port": settings.serial_port,
            "baudrate": settings.baudrate,
            "parity": settings.parity,
            "function": adc_hit.get("function"),
        },
        "slave_address_register_0x4000": config.get("device_id"),
        "uart_register_0x2000": {
            "baudrate": config.get("baudrate"),
            "parity": config.get("parity"),
        },
    }


def _resolve_waveshare_ports(ports: "dict[str, Any]") -> "tuple[str, str]":
    """Return (io_port, adc_port) resolving fallbacks from settings."""
    io_port = ports["io_serial_port"] or str(_settings.modbus_serial_port)
    adc_port = ports["adc_serial_port"] or io_port
    return io_port, adc_port


def _split_hits_by_role(hits: list) -> "tuple[list, list]":
    """Split scan hits into (io_hits, adc_hits) by role field."""
    io_hits = [h for h in hits if h.get("role") == "modbus-io"]
    adc_hits = [h for h in hits if h.get("role") == "modbus-adc"]
    return io_hits, adc_hits


def _build_waveshare_diagnose_report(health: dict[str, Any] | None = None) -> dict[str, Any]:
    baud_sequence = [4800, 9600, 19200, 38400, 57600, 115200]
    io_ids = _modbus_io_device_ids()
    adc_id = int(_settings.modbus_adc_device_id)
    target_ids = sorted(set([*io_ids, adc_id]))
    ports = _modbus_runtime_serial_ports()
    separate = ports["topology"] == "separate-adapters"
    io_port, adc_port = _resolve_waveshare_ports(ports)

    target_baud = int(_settings.modbus_baud)
    target_parity = str(_settings.modbus_parity)
    io_device_id = int(_settings.modbus_device_id)

    if _modbus_plugins_healthy(health):
        return _build_waveshare_from_plugin_health(
            health or {},
            ports=ports,
            io_ids=io_ids,
            adc_id=adc_id,
            target_baud=target_baud,
            target_parity=target_parity,
            baud_sequence=baud_sequence,
        )

    if _modbus_health_serial_stale(health):
        return _build_waveshare_serial_stale_report(
            health or {},
            ports=ports,
            io_ids=io_ids,
            adc_id=adc_id,
            baud_sequence=baud_sequence,
        )

    try:
        import pimodbus.config  # noqa: F401
        import pimodbus.provisioning  # noqa: F401
    except Exception as exc:
        return {
            "ok": False,
            "error": f"pimodbus is not available: {exc}",
            "baud_sequence": baud_sequence,
            "io_device_ids": io_ids,
            "adc_device_id": adc_id,
            "topology": ports["topology"],
        }

    if separate:
        report_dict, report_ok = _probe_waveshare_separate(
            io_port, adc_port, target_baud, target_parity, io_device_id, io_ids, adc_id
        )
    else:
        report_dict, report_ok = _probe_waveshare_shared_bus(
            io_port, target_baud, target_parity, io_device_id, adc_id, target_ids
        )

    hits = list(report_dict.get("hits") or [])
    io_hits, adc_hits = _split_hits_by_role(hits)

    per_slave: dict[str, Any] = {}
    for io_id in io_ids:
        per_slave[f"modbus-io-{io_id}"] = _read_waveshare_io_slave_config(
            io_id, io_hits, io_port, target_baud, target_parity
        )

    per_slave[f"modbus-adc-{adc_id}"] = _read_waveshare_adc_slave_config(
        adc_id, adc_hits, adc_port, target_baud, target_parity
    )

    return {
        "ok": report_ok,
        "baud_sequence": baud_sequence,
        "io_device_ids": io_ids,
        "adc_device_id": adc_id,
        "topology": ports["topology"],
        "io_serial_port": io_port,
        "adc_serial_port": adc_port,
        "waveshare_scan": report_dict,
        "per_slave": per_slave,
    }


def _modbus_wizard_target_ids() -> list[int]:
    return sorted(set([*_modbus_io_device_ids(), int(_settings.modbus_adc_device_id)]))


def _modbus_wizard_plan() -> dict[str, Any]:
    io_ids = _modbus_io_device_ids()
    adc_id = int(_settings.modbus_adc_device_id)
    ports = _modbus_runtime_serial_ports()
    io_port = ports["io_serial_port"] or str(_settings.modbus_serial_port)
    adc_port = ports["adc_serial_port"] or io_port
    separate = ports["topology"] == "separate-adapters"
    target_baud = int(_settings.modbus_baud)
    target_parity = str(_settings.modbus_parity).upper()

    configure_steps: list[dict[str, Any]] = []
    for io_id in io_ids:
        configure_steps.append(
            {
                "step": f"configure-modbus-io-{io_id}",
                "serial_port": io_port,
                "instruction": (
                    f"Podlacz tylko modul Modbus IO na adapterze RS485 ({io_port}). "
                    "Odizoluj pozostale moduly od A/B."
                    if separate
                    else f"Podlacz tylko modul Modbus IO na RS485 ({io_port}). "
                    "Odizoluj pozostale moduly od A/B."
                ),
                "program_target": {
                    "module_role": "modbus-io",
                    "serial_port": io_port,
                    "new_device_id": io_id,
                    "new_baudrate": target_baud,
                    "new_parity": target_parity,
                },
            }
        )
    configure_steps.append(
        {
            "step": f"configure-modbus-adc-{adc_id}",
            "serial_port": adc_port,
            "instruction": (
                f"Podlacz tylko modul Modbus ADC na osobnym adapterze RS485 ({adc_port}). "
                "Odizoluj pozostale moduly od A/B."
                if separate
                else f"Podlacz tylko modul Modbus ADC na RS485 ({adc_port}). "
                "Odizoluj pozostale moduly od A/B."
            ),
            "program_target": {
                "module_role": "modbus-adc",
                "serial_port": adc_port,
                "new_device_id": adc_id,
                "new_baudrate": target_baud,
                "new_parity": target_parity,
            },
        }
    )
    configure_steps.append(
        {
            "step": "final-check-all-connected",
            "instruction": (
                "Oba moduly podlaczone do swoich adapterow USB (IO i ADC osobno) — uruchom finalna diagnostyke."
                if separate
                else "Podlacz wszystkie moduly razem i uruchom waveshare-diagnose."
            ),
            "verify_endpoint": "/api/v1/hardware/modbus/waveshare-diagnose",
        }
    )

    return {
        "ok": True,
        "serial_port": io_port,
        "io_serial_port": io_port,
        "adc_serial_port": adc_port,
        "topology": ports["topology"],
        "topology_mode": ports.get("topology_mode", "auto"),
        "target_baudrate": target_baud,
        "target_parity": target_parity,
        "target_ids": _modbus_wizard_target_ids(),
        "steps": configure_steps,
    }


def _collect_wizard_serial_candidates(serial_port: str) -> list[str]:
    """Build list of serial ports to probe, starting with any explicit port."""
    requested = str(serial_port or "").strip()
    if requested:
        return [requested]
    candidates: list[str] = []
    for value in [str(_settings.modbus_serial_port), str(_settings.modbus_adc_serial_port)]:
        value = str(value or "").strip()
        if value and value not in candidates:
            candidates.append(value)
    for discovered in sorted(
        glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*") + glob.glob("/dev/serial/by-id/*")
    ):
        if discovered and discovered not in candidates:
            candidates.append(discovered)
    return candidates


def _modbus_wizard_probe_isolated(
    serial_port: str,
    baudrates: list[int],
    parities: list[str],
    device_ids: list[int],
    required_roles: list[str] | None = None,
) -> dict[str, Any]:
    try:
        from pimodbus.repair import diagnose_shared_bus
    except Exception as exc:
        return {"ok": False, "error": f"pimodbus is not available: {exc}"}

    serial_candidates = _collect_wizard_serial_candidates(serial_port)

    all_scans: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    active_serial = serial_port
    for serial in serial_candidates:
        report = diagnose_shared_bus(
            serial_port=serial,
            target_baudrate=int(_settings.modbus_baud),
            target_parity=str(_settings.modbus_parity),
            io_device_id=int(_settings.modbus_device_id),
            adc_device_id=int(_settings.modbus_adc_device_id),
            baudrates=baudrates,
            parities=parities,
            device_ids=device_ids,
            timeout=1.0,
            scan_all_ports=False,
            required_roles=required_roles,
        )
        report_dict = report.to_dict()
        all_scans.append({"serial_port": serial, "scan": report_dict})
        hits = list(report_dict.get("hits") or [])
        current_candidates = [
            {
                "role": hit.get("role"),
                "device_id": int(hit.get("device_id", 0)),
                "baudrate": int(hit.get("baudrate", 0)),
                "parity": str(hit.get("parity") or ""),
                "serial_port": str(hit.get("serial_port") or serial),
            }
            for hit in hits
        ]
        if current_candidates:
            candidates = current_candidates
            active_serial = serial
            break

    report_dict = all_scans[-1]["scan"] if all_scans else {"ok": False, "hits": [], "issues": []}
    return {
        "ok": bool(candidates),
        "serial_port": active_serial,
        "candidates": candidates,
        "scan": report_dict,
        "all_scans": all_scans,
    }


def _wizard_check_already_configured(
    existing: "dict[str, Any]",
    new_device_id: int,
    new_baudrate: int,
    line_parity: str,
) -> bool:
    """Return True when existing device config already matches the target settings."""
    existing_id = int(existing.get("device_id") or -1)
    existing_baud = int(existing.get("baudrate") or 0)
    existing_parity = str(existing.get("parity") or "").upper()
    return (
        existing_id == int(new_device_id)
        and existing_baud == int(new_baudrate)
        and existing_parity == line_parity
    )


def _wizard_apply_uart_write(
    bus_settings: Any,
    cur_id: int,
    new_id: int,
    uart_target: int,
    new_baudrate: int,
    line_parity: str,
    write_uart_config: Any,
    write_device_address: Any,
    _uart_register_value: Any,
) -> "dict[str, bool]":
    """Write UART config and device address with retry loop. Returns {set_address, set_uart}."""
    import time

    uart_at_current = _uart_register_value(cur_id)
    if uart_at_current is not None and int(uart_at_current) == int(uart_target):
        set_uart = True
    else:
        set_uart = bool(
            write_uart_config(
                bus_settings,
                device_id=cur_id,
                baudrate=int(new_baudrate),
                parity=line_parity,
            )
        )

    if cur_id != new_id:
        set_address = bool(
            write_device_address(
                bus_settings,
                current_device_id=cur_id,
                new_device_id=new_id,
            )
        )
        time.sleep(0.2)
    else:
        set_address = True

    if not set_uart:
        for attempt, device_id in enumerate((new_id, new_id, cur_id)):
            if attempt == 1:
                time.sleep(0.15)
            uart_value = _uart_register_value(device_id)
            if uart_value is not None and int(uart_value) == int(uart_target):
                set_uart = True
                break
        if not set_uart:
            set_uart = bool(
                write_uart_config(
                    bus_settings,
                    device_id=new_id,
                    baudrate=int(new_baudrate),
                    parity=line_parity,
                )
            )

    return {"set_address": set_address, "set_uart": set_uart}


def _wizard_verify_config(
    read_device_config: Any,
    verify_settings: Any,
    new_device_id: int,
    new_baudrate: int,
    line_parity: str,
) -> "tuple[bool, dict, str]":
    """Read back device config after programming; return (verified, verify_dict, error_str)."""
    verify_error = ""
    try:
        verify = read_device_config(verify_settings, device_id=new_device_id).to_dict()
    except Exception as exc:
        verify = {}
        verify_error = str(exc)
    verified = (
        int(verify.get("device_id") or -1) == new_device_id
        and int(verify.get("baudrate") or 0) == new_baudrate
        and str(verify.get("parity") or "").upper() == line_parity
    )
    return verified, verify, verify_error


def _wizard_build_result(
    writes: dict,
    verify: dict,
    verified: bool,
    new_device_id: int,
    new_baudrate: int,
    line_parity: str,
    serial_port: str,
    verify_error: str,
) -> dict:
    """Build the response dict for _modbus_wizard_program_isolated."""
    ok = bool(verified or (writes["set_address"] and writes["set_uart"]))
    result: dict[str, Any] = {
        "ok": ok,
        "writes": writes,
        "verify": verify,
        "target": {
            "device_id": new_device_id,
            "baudrate": new_baudrate,
            "parity": line_parity,
            "serial_port": serial_port,
        },
        "verified": bool(verified),
    }
    if verify_error and not ok:
        result["error"] = verify_error
    return result


def _modbus_wizard_program_isolated(
    *,
    serial_port: str,
    current_device_id: int,
    new_device_id: int,
    new_baudrate: int,
    new_parity: str,
    confirm_isolated: bool,
) -> dict[str, Any]:
    if not confirm_isolated:
        return {
            "ok": False,
            "error": "Refusing to write Modbus configuration without confirm_isolated=true",
        }
    try:
        from pimodbus.config import RtuBusSettings
        from pimodbus.provisioning import (
            UART_REGISTER,
            read_device_config,
            uart_register_value,
            write_device_address,
            write_uart_config,
            _open_client,
            _read_holding_register,
        )
    except Exception as exc:
        return {"ok": False, "error": f"pimodbus is not available: {exc}"}

    line_parity = str(new_parity).upper()
    bus_settings = RtuBusSettings(
        serial_port=serial_port,
        baudrate=int(new_baudrate),
        parity=line_parity,
        timeout=2.0,
    )

    verify_settings = bus_settings
    config_read_error = ""
    try:
        existing = read_device_config(verify_settings, device_id=int(current_device_id)).to_dict()
    except Exception as exc:
        config_read_error = str(exc)
        if int(current_device_id) == int(new_device_id):
            return {
                "ok": True,
                "verified": False,
                "writes": {
                    "set_address": True,
                    "set_uart": True,
                    "skipped": True,
                    "config_read_error": config_read_error,
                },
                "verify": {},
                "target": {
                    "device_id": int(new_device_id),
                    "baudrate": int(new_baudrate),
                    "parity": line_parity,
                    "serial_port": serial_port,
                },
                "note": "Probe reported target slave ID; skipped provisioning writes (config registers unreadable).",
            }
        return {"ok": False, "error": config_read_error}

    already_configured = _wizard_check_already_configured(existing, new_device_id, new_baudrate, line_parity)

    writes: dict[str, Any] = {
        "set_address": False,
        "set_uart": False,
        "skipped": already_configured,
    }
    if already_configured:
        writes["set_address"] = True
        writes["set_uart"] = True
    else:
        uart_target = uart_register_value(int(new_baudrate), line_parity)
        cur_id = int(current_device_id)
        new_id = int(new_device_id)

        def _uart_register_value(device_id: int) -> int | None:
            client = _open_client(bus_settings)
            try:
                return _read_holding_register(client, UART_REGISTER, device_id)
            finally:
                client.close()

        write_results = _wizard_apply_uart_write(
            bus_settings, cur_id, new_id, uart_target, new_baudrate, line_parity,
            write_uart_config, write_device_address, _uart_register_value,
        )
        writes["set_address"] = write_results["set_address"]
        writes["set_uart"] = write_results["set_uart"]

    verified, verify, verify_error = _wizard_verify_config(
        read_device_config, verify_settings, int(new_device_id), int(new_baudrate), line_parity
    )
    return _wizard_build_result(
        writes, verify, verified,
        int(new_device_id), int(new_baudrate), line_parity, serial_port, verify_error,
    )


def set_hardware_gateway(gw: HardwareGateway) -> None:
    global _gateway
    _gateway = gw


def _gw() -> HardwareGateway:
    if _gateway is None:
        raise RuntimeError("HardwareGateway not initialised")
    return _gateway


def _hardware_health_overall_ok(payload: dict[str, Any]) -> bool:
    """True when every enabled plugin entry in the health payload is compatible."""
    skip_keys = {
        "mode",
        "note",
        "platform",
        "modbus",
        "overall_ok",
        "degraded",
        "init_summary",
    }
    for key, entry in payload.items():
        if key in skip_keys or not isinstance(entry, dict):
            continue
        if entry.get("status") == "disabled":
            continue
        if entry.get("compatible") is not True:
            return False
    return True


@router.get("/health")
async def hardware_health():
    """Return connectivity status for all hardware services."""
    payload = await _gw().health()
    if isinstance(payload, dict):
        payload["platform"] = _detect_runtime_platform()
        if payload.get("mode") == "real":
            overall_ok = _hardware_health_overall_ok(payload)
            payload["overall_ok"] = overall_ok
            payload["degraded"] = not overall_ok
            if not overall_ok:
                payload["status"] = "degraded"
    return payload


def _determine_scan_set(
    scan_mode: str, health: "dict[str, Any]"
) -> tuple["set[str]", bool, str]:
    """
    Compute the set of adapter IDs that need a live scan probe.
    Returns (scan_ids, skipped_owned_modbus, skip_reason).
    """
    scan_ids: set[str] = set()
    skipped_owned_modbus_probe = False
    scan_skip_reason = "plugin-health compatible" if scan_mode == "auto" else "scan=never"

    if scan_mode == "always":
        scan_ids = {hw["id"] for hw in _HARDWARE_REGISTRY}
    elif scan_mode == "auto" and _needs_live_scan(health):
        scan_ids = _unhealthy_plugin_ids(health)

    for plugin_key in ("modbus-io", "modbus-adc"):
        plugin_health = health.get(plugin_key)
        if isinstance(plugin_health, dict) and _modbus_health_is_no_response(plugin_health):
            skipped_owned_modbus_probe = plugin_key in scan_ids or skipped_owned_modbus_probe
            scan_ids.discard(plugin_key)

    if skipped_owned_modbus_probe:
        scan_skip_reason = "plugin owns Modbus serial port; skipped duplicate no-response probe"

    return scan_ids, skipped_owned_modbus_probe, scan_skip_reason


def _map_adapter_identify_status(
    hw: "dict[str, Any]",
    health: "dict[str, Any]",
    probes: "dict[str, Any]",
) -> "dict[str, Any]":
    """Build the adapter entry dict with status based on health and probe results."""
    hw_id = hw["id"]
    probe = probes.get(hw_id, {})
    health_entry = health.get(hw_id)
    entry = {**hw, "status": "offline", "probe": probe}

    if isinstance(health_entry, dict):
        entry["probe"] = {
            "connected": bool(health_entry.get("compatible")),
            "source": "plugin-health",
            "health": health_entry,
            "local_probe": probe,
        }
        if health_entry.get("compatible"):
            entry["status"] = "ok"
        elif health_entry.get("status") == "error":
            if hw_id in {"modbus-io", "modbus-adc"} and _modbus_health_is_no_response(health_entry):
                entry["status"] = "adapter-only"
                entry["probe"]["diagnosis"] = (
                    "serial adapter is open in OqlOS, but the Modbus device did not answer"
                )
            else:
                entry["status"] = "no-access"
        else:
            entry["status"] = "offline"
    elif probe.get("connected"):
        if hw_id in {"modbus-io", "modbus-adc"} and not probe.get("modbus_device_responds", True):
            entry["status"] = "adapter-only"
        else:
            entry["status"] = "ok"
    elif probe.get("reason"):
        entry["status"] = "no-access"
    else:
        entry["status"] = "offline"

    return entry


@router.get("/identify")
async def hardware_identify(
    scan: str = Query(
        default="never",
        description="Scan mode: auto (scan only on failure), always (force live scan), never (skip live scan)",
    )
):
    """Return hardware identification with conditional live scanning for low latency."""
    scan_mode_raw = scan if isinstance(scan, str) else "never"
    scan_mode = (scan_mode_raw or "never").strip().lower()
    if scan_mode not in {"auto", "always", "never"}:
        scan_mode = "never"

    health = await _gw().health()
    scan_ids, skipped_owned_modbus_probe, scan_skip_reason = _determine_scan_set(scan_mode, health)
    should_scan = bool(scan_ids)

    if should_scan:
        probes_task = asyncio.to_thread(_probe_selected_hardware, scan_ids)
        diagnostics_task = asyncio.to_thread(_collect_hardware_diagnostics)
        probes, diagnostics = await asyncio.gather(probes_task, diagnostics_task)
    else:
        probes = {}
        diagnostics = {"scan_skipped": True, "scan_skip_reason": scan_skip_reason}

    adapters = [_map_adapter_identify_status(hw, health, probes) for hw in _HARDWARE_REGISTRY]

    mode = health.get("mode", "mock")
    payload = {
        "mode": mode,
        "platform": _detect_runtime_platform(),
        "detected": sum(1 for a in adapters if a["status"] == "ok"),
        "total": len(adapters),
        "adapters": adapters,
        "diagnostics": {
            "health": health,
            "scan_mode": scan_mode,
            "scan_performed": should_scan,
            "modbus_preflight": _modbus_preflight_report(),
            "modbus_repair": _modbus_repair_guidance(health),
            **diagnostics,
        },
    }
    return enrich_identify_payload(payload)


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


@router.get("/hui/actions")
async def hui_actions() -> dict[str, Any]:
    """Return OqlOS-owned HUI action recipes."""
    return list_hui_actions()


@router.post("/hui/shutdown", summary="Stop HUI pump/valve actions using the canonical OqlOS recipe")
async def hui_shutdown() -> dict[str, Any]:
    return await shutdown_all_hui_hardware(_gw())


def _raise_if_hui_failed(payload: dict[str, Any]) -> None:
    if not payload.get("ok"):
        raise HTTPException(status_code=400, detail=payload)


async def _start_hui_action(action: Any, *args: Any) -> dict[str, Any]:
    payload = await action(_gw(), *args)
    _raise_if_hui_failed(payload)
    return payload


@router.post("/hui/hold/{key}/start", summary="Start a named HUI hold action")
async def hui_hold_start(key: str) -> dict[str, Any]:
    return await _start_hui_action(start_hui_hold, key)


@router.post("/hui/hold/{key}/stop", summary="Stop a named HUI hold action and return hardware to a safe state")
async def hui_hold_stop(key: str) -> dict[str, Any]:
    return await stop_hui_hold(_gw(), key)


@router.post("/hui/al/start", summary="Start the HUI artificial-lung action")
async def hui_al_start() -> dict[str, Any]:
    return await _start_hui_action(start_hui_artificial_lung)


@router.post("/hui/al/stop", summary="Stop the HUI artificial-lung action")
async def hui_al_stop() -> dict[str, Any]:
    return await stop_hui_artificial_lung(_gw())


@router.get("/sensor/{sensor_id}")
async def read_sensor(sensor_id: str):
    """Read a sensor value directly from hardware."""
    health = await _gw().health()
    modbus_adc_health = health.get("modbus-adc")
    if health.get("mode") == "real" and isinstance(modbus_adc_health, dict) and not modbus_adc_health.get("compatible"):
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Modbus ADC is not available for real sensor readings",
                "sensor_id": sensor_id,
                "modbus_adc": modbus_adc_health,
            },
        )

    value = await _gw().read_sensor(sensor_id)
    return {"sensor_id": sensor_id, "value": value}


def _read_cpu_temperature() -> dict[str, Any]:
    """Best-effort CPU temperature read for HUI status panels."""
    thermal_paths = [
        pathlib.Path("/sys/class/thermal/thermal_zone0/temp"),
        *sorted(pathlib.Path("/sys/class/thermal").glob("thermal_zone*/temp")),
    ]
    seen: set[pathlib.Path] = set()
    for path in thermal_paths:
        if path in seen:
            continue
        seen.add(path)
        try:
            raw = path.read_text(encoding="utf-8").strip()
            if not raw:
                continue
            temp_millidegrees = float(raw)
        except (OSError, ValueError):
            continue
        return {
            "cpu_temp_celsius": round(temp_millidegrees / 1000, 1),
            "source": str(path),
            "available": True,
        }
    try:
        output = subprocess.run(
            ["vcgencmd", "measure_temp"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if output.returncode == 0:
            temp_text = output.stdout.strip()
            if "temp=" in temp_text:
                temp_value = temp_text.split("temp=", 1)[1].split("'", 1)[0]
                return {
                    "cpu_temp_celsius": round(float(temp_value), 1),
                    "source": "vcgencmd",
                    "available": True,
                }
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return {
        "cpu_temp_celsius": None,
        "source": None,
        "available": False,
    }


@router.get("/temperature")
async def hardware_temperature() -> dict[str, Any]:
    """Read CPU temperature, returning an HUI-compatible unavailable payload if absent."""
    temp_data = _read_cpu_temperature()
    return {
        "ok": bool(temp_data["available"]),
        "peripheral_id": "cpu-temperature",
        "command": "read_temperature",
        **({"error": "Temperature sensor not available"} if not temp_data["available"] else {}),
        "result": {
            "success": bool(temp_data["available"]),
            "data": temp_data,
        },
    }


@router.get("/sensors/batch")
async def read_sensors_batch(
    sensor_ids: str = Query(
        default="ai01,ai02,ai03",
        description="Comma-separated sensor IDs",
    ),
) -> dict[str, Any]:
    """Read multiple sensors without making HUI fall back to repeated failing requests."""
    ids = [sensor_id.strip() for sensor_id in sensor_ids.split(",") if sensor_id.strip()]
    health = await _gw().health()
    modbus_adc_health = health.get("modbus-adc")
    modbus_unavailable = (
        health.get("mode") == "real"
        and isinstance(modbus_adc_health, dict)
        and not modbus_adc_health.get("compatible")
    )

    sensors: dict[str, dict[str, Any]] = {}
    for sensor_id in ids:
        if modbus_unavailable:
            sensors[sensor_id] = {
                "sensor_id": sensor_id,
                "value": None,
                "ok": False,
                "error": "Modbus ADC is not available for real sensor readings",
                "modbus_adc": modbus_adc_health,
            }
            continue
        try:
            value = await _gw().read_sensor(sensor_id)
            sensors[sensor_id] = {
                "sensor_id": sensor_id,
                "value": value,
                "ok": value is not None,
            }
        except Exception as exc:
            sensors[sensor_id] = {
                "sensor_id": sensor_id,
                "value": None,
                "ok": False,
                "error": str(exc),
            }

    return {
        "ok": all(sensor.get("ok") for sensor in sensors.values()) if sensors else False,
        "sensors": sensors,
        "diagnostics": {
            "mode": health.get("mode"),
            **({"modbus_adc": modbus_adc_health} if modbus_unavailable else {}),
        },
    }


@router.get("/diagnose")
async def hardware_diagnose() -> dict[str, Any]:
    """Return HUI-friendly hardware diagnostics without failing the request."""
    try:
        health = await _gw().health()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    modbus_adc_health = health.get("modbus-adc")
    modbus_unavailable = (
        health.get("mode") == "real"
        and isinstance(modbus_adc_health, dict)
        and not modbus_adc_health.get("compatible")
    )
    sensors: dict[str, dict[str, Any]] = {}
    for sensor_id in ("ai01", "ai02", "ai03"):
        if modbus_unavailable:
            sensors[sensor_id] = {
                "sensor_id": sensor_id,
                "value": None,
                "ok": False,
                "error": "Modbus ADC is not available for real sensor readings",
                "modbus_adc": modbus_adc_health,
            }
            continue
        try:
            value = await _gw().read_sensor(sensor_id)
            sensors[sensor_id] = {"sensor_id": sensor_id, "value": value, "ok": value is not None}
        except Exception as exc:
            sensors[sensor_id] = {
                "sensor_id": sensor_id,
                "value": None,
                "ok": False,
                "error": str(exc),
            }

    return {
        "ok": True,
        "gateway_mode": health.get("mode", "unknown"),
        "gateway_health": health,
        "sensors": sensors,
    }


@router.get("/modbus/waveshare-diagnose")
async def hardware_modbus_waveshare_diagnose() -> dict[str, Any]:
    """Run Waveshare-focused Modbus scan matrix and per-slave register checks."""
    health = await _gw().health()
    return await asyncio.to_thread(_build_waveshare_diagnose_report, health)


@router.get("/stack/snapshot")
async def hardware_stack_snapshot() -> dict[str, Any]:
    """Single autodetect + configuration-cycle snapshot (health, ports, wizard plan)."""
    from oqlos.hardware.stack_snapshot import build_hardware_stack_snapshot

    health = await _gw().health()
    return await asyncio.to_thread(build_hardware_stack_snapshot, health)


@router.get("/diagnosis")
async def hardware_diagnosis_route(
    scan: str = Query(default="never", description="Identify scan mode passed before diagnosis"),
) -> dict[str, Any]:
    """Per-device diagnosis plan (environment + recommended actions)."""
    from oqlos.hardware.diagnosis import build_diagnosis_report, report_to_dict

    identify_payload = await hardware_identify(scan=scan)
    report = build_diagnosis_report(identify_payload)
    return report_to_dict(report)


@router.post("/recover")
async def hardware_recover_route(
    scope: str = Query(default="safe", description="Recovery scope: safe = in-process plugin reconnect only"),
) -> dict[str, Any]:
    """Safe auto-recovery inside OqlOS; host sidecar steps are returned as host_actions."""
    from oqlos.hardware.diagnosis import build_diagnosis_report, execute_safe_recover, report_to_dict

    if scope.strip().lower() != "safe":
        raise HTTPException(status_code=400, detail="Only scope=safe is supported via API")
    identify_payload = await hardware_identify(scan="never")
    report = build_diagnosis_report(identify_payload)
    execution = await execute_safe_recover(_gw(), report)
    return {
        **execution,
        "device_diagnosis": report_to_dict(report),
        "source": "oqlos.hardware.recover",
    }


@router.get("/modbus/wizard/plan")
async def hardware_modbus_wizard_plan() -> dict[str, Any]:
    """Return guided step-by-step Modbus configuration plan."""
    return await asyncio.to_thread(_modbus_wizard_plan)


@router.post("/modbus/wizard/probe-isolated")
async def hardware_modbus_wizard_probe_isolated(
    serial_port: str = Body(default=""),
    baudrates: list[int] | None = Body(default=None),
    parities: list[str] | None = Body(default=None),
    device_ids: list[int] | None = Body(default=None),
    module_role: str = Body(default=""),
) -> dict[str, Any]:
    """Probe one isolated module before writing address/UART settings."""
    serial = serial_port or str(_settings.modbus_serial_port)
    # Waveshare IO/ADC default 9600 N — probe it before legacy high-speed guesses.
    scan_bauds = baudrates or [9600, 4800, 19200, 38400, 57600, 115200]
    scan_parities = [str(value).upper() for value in (parities or ["N", "E", "O"])]
    scan_ids = device_ids or [1, 2, 3, 4, 5, 8, 16, 32, 64, 128, 247]
    role = str(module_role or "").strip()
    required_roles = [role] if role in {"modbus-io", "modbus-adc"} else None
    return await asyncio.to_thread(
        _modbus_wizard_probe_isolated,
        serial,
        scan_bauds,
        scan_parities,
        scan_ids,
        required_roles,
    )


@router.post("/modbus/wizard/program-isolated")
async def hardware_modbus_wizard_program_isolated(
    serial_port: str = Body(default=""),
    current_device_id: int = Body(default=1),
    new_device_id: int = Body(default=1),
    new_baudrate: int = Body(default=9600),
    new_parity: str = Body(default="N"),
    confirm_isolated: bool = Body(default=False),
) -> dict[str, Any]:
    """Program one isolated module (address + UART), then verify config."""
    serial = serial_port or str(_settings.modbus_serial_port)
    return await asyncio.to_thread(
        _modbus_wizard_program_isolated,
        serial_port=serial,
        current_device_id=int(current_device_id),
        new_device_id=int(new_device_id),
        new_baudrate=int(new_baudrate),
        new_parity=str(new_parity).upper(),
        confirm_isolated=bool(confirm_isolated),
    )


@router.get("/modbus-adc/raw")
async def read_modbus_adc_raw() -> dict[str, Any]:
    """Return raw Modbus ADC diagnostics for HUI troubleshooting."""
    try:
        health = await _gw().health()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    modbus_adc_health = health.get("modbus-adc")
    if not isinstance(modbus_adc_health, dict):
        return {
            "ok": False,
            "error": "modbus-adc health not available",
            "gateway_mode": health.get("mode"),
            "gateway_health": health,
        }
    if not modbus_adc_health.get("compatible"):
        return {
            "ok": False,
            "error": "modbus-adc not compatible",
            "gateway_mode": health.get("mode"),
            "modbus_adc_health": modbus_adc_health,
        }

    try:
        plugin = await _gw()._get_or_connect_plugin("modbus-adc")
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "gateway_mode": health.get("mode"),
            "modbus_adc_health": modbus_adc_health,
        }
    if not plugin:
        return {
            "ok": False,
            "error": "modbus-adc plugin not available",
            "gateway_mode": health.get("mode"),
            "modbus_adc_health": modbus_adc_health,
        }

    result = await plugin.execute_command("read_all", {})
    if not result.get("success"):
        return {
            "ok": False,
            "error": result.get("error", "Unknown error from modbus-adc plugin"),
            "gateway_mode": health.get("mode"),
            "modbus_adc_health": modbus_adc_health,
            "plugin_result": result,
        }

    return {
        "ok": True,
        "gateway_mode": health.get("mode"),
        "modbus_adc_config": {
            "serial_port": getattr(plugin.config, "serial_port", "unknown"),
            "baudrate": getattr(plugin.config, "baudrate", "unknown"),
            "device_id": getattr(plugin.config, "device_id", "unknown"),
        },
        "raw_data": result.get("data", {}),
    }


@router.post("/lung")
async def set_lung(steps: int = 500, speed: int = TIC249_DEFAULT_TARGET_VELOCITY, cycles: int = 5, pause: float = 0.5):
    """Start artificial lung reciprocating motion (tic249 stepper)."""
    detailed_result: dict[str, Any] | None = None
    if hasattr(_gw(), "set_lung_result"):
        try:
            maybe_result = await _gw().set_lung_result(steps=steps, speed=speed, cycles=cycles, pause=pause)
            if isinstance(maybe_result, dict):
                detailed_result = maybe_result
        except Exception:
            detailed_result = None

    if detailed_result is None:
        ok = await _gw().set_lung(steps=steps, speed=speed, cycles=cycles, pause=pause)
        return {"steps": steps, "speed": speed, "cycles": cycles, "pause": pause, "ok": ok}

    payload: dict[str, Any] = {
        "steps": steps,
        "speed": speed,
        "cycles": cycles,
        "pause": pause,
        "ok": bool(detailed_result.get("success", False)),
    }
    if detailed_result.get("error"):
        payload["error"] = detailed_result.get("error")
    if detailed_result.get("data") is not None:
        payload["data"] = detailed_result.get("data")
    return payload


async def _lung_state_response(action: Any, status: str) -> dict[str, Any]:
    ok = await action()
    return {"ok": ok, "status": status}


@router.post("/lung/stop", summary="Emergency stop the artificial lung motor")
async def stop_lung():
    return await _lung_state_response(_gw().stop_lung, "stopped")


@router.post("/lung/disable", summary="De-energize the artificial lung motor")
async def disable_lung():
    return await _lung_state_response(_gw().disable_lung, "de-energized")


@router.get("/artificial-lung/status")
async def artificial_lung_status():
    """Logical lung state merged with motor connectivity hints."""
    return await get_artificial_lung_status(_gw())


@router.post("/artificial-lung/command")
async def artificial_lung_command(payload: dict[str, Any] = Body(default_factory=dict)):
    """Execute artificial-lung logical commands (set_lpm, lung_*, emergency_stop)."""
    command, args = _command_payload(payload)
    return await execute_artificial_lung_command(command, args, _gw())


def _command_payload(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    command = str(payload.get("command") or "").strip()
    if not command:
        raise HTTPException(status_code=400, detail="command is required")
    args = payload.get("args")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise HTTPException(status_code=400, detail="args must be an object")
    return command, args


@router.get("/rtc/status")
async def rtc_status():
    """Return runtime status for the RTC sidecar."""
    return await asyncio.to_thread(build_rtc_peripheral_status)


@router.post("/rtc/command")
async def rtc_command(payload: dict[str, Any] = Body(default_factory=dict)):
    """Execute a diagnostic command against the RTC sidecar."""
    command, args = _command_payload(payload)
    return await asyncio.to_thread(run_rtc_command, command, args)
