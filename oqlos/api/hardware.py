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
import sys
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from oqlos.config import get_settings
from oqlos.hardware.discovery import list_serial_ports, probe_waveshare_modbus, probe_waveshare_modbus_adc
from oqlos.hardware.artificial_lung import execute_command as execute_artificial_lung_command
from oqlos.hardware.artificial_lung import get_peripheral_status as get_artificial_lung_status
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


def _detect_runtime_platform() -> dict[str, Any]:
    board_model = _board_model()
    os_release = _os_release()
    system = platform.system() or "unknown"
    is_wsl = "microsoft" in platform.release().lower()
    in_container = _in_container()
    is_rpi = "raspberry pi" in board_model.lower()

    if is_rpi:
        detected = "raspberry-pi"
    elif system == "Linux" and in_container:
        detected = "linux-container"
    elif system == "Linux" and is_wsl:
        detected = "wsl"
    elif system == "Linux":
        detected = "desktop-linux"
    elif system == "Darwin":
        detected = "macos"
    elif system == "Windows":
        detected = "windows"
    else:
        detected = "unknown"

    piadc_selected = _selected_piadc_platform()
    modbus_adc_serial = (
        os.getenv("OQLOS_MODBUS_ADC_SERIAL_PORT")
        or os.getenv("MODBUS_ADC_SERIAL_PORT")
        or os.getenv("OQLOS_MODBUS_BUS_SERIAL_PORT")
        or os.getenv("MODBUS_BUS_SERIAL_PORT")
        or _settings.modbus_adc_serial_port
    )
    modbus_io_serial = (
        os.getenv("OQLOS_MODBUS_SERIAL_PORT")
        or os.getenv("MODBUS_SERIAL_PORT")
        or os.getenv("OQLOS_MODBUS_BUS_SERIAL_PORT")
        or os.getenv("MODBUS_BUS_SERIAL_PORT")
        or _settings.modbus_serial_port
    )

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
        "modbus_bus_serial_port": modbus_io_serial if modbus_io_serial == modbus_adc_serial else "",
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


def _probe_modbus_rtu() -> dict[str, Any]:
    """Detect the active Waveshare Modbus RTU serial port and line settings."""
    probe = probe_waveshare_modbus(
        preferred_port=_settings.modbus_serial_port,
        preferred_baud=_settings.modbus_baud,
        preferred_parity=_settings.modbus_parity,
        preferred_device_id=_settings.modbus_device_id,
    )
    if probe.get("connected") and not probe.get("modbus_device_responds", True):
        note = probe.get("note") or "USB serial adapter detected"
        probe["note"] = f"{note} (check power or RS485 wiring if this is unexpected)"
    return probe


def _probe_modbus_adc_rtu() -> dict[str, Any]:
    """Detect the Waveshare Modbus RTU Analog Input 8CH module."""
    probe = probe_waveshare_modbus_adc(
        preferred_port=_settings.modbus_adc_serial_port,
        preferred_baud=_settings.modbus_adc_baud,
        preferred_parity=_settings.modbus_adc_parity,
        preferred_device_id=_settings.modbus_adc_device_id,
    )
    if probe.get("connected") and not probe.get("modbus_device_responds", True):
        note = probe.get("note") or "USB serial adapter detected"
        probe["note"] = f"{note} (check power, address, baudrate, or RS485 wiring if this is unexpected)"
    return probe


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
        results["modbus-adc"] = _probe_modbus_adc_rtu()
    if "modbus-io" in selected:
        results["modbus-io"] = _probe_modbus_rtu()
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
    payload = await _gw().health()
    if isinstance(payload, dict):
        payload["platform"] = _detect_runtime_platform()
    return payload


@router.get("/identify")
async def hardware_identify(
    scan: str = Query(
        default="auto",
        description="Scan mode: auto (scan only on failure), always (force live scan), never (skip live scan)",
    )
):
    """Return hardware identification with conditional live scanning for low latency."""
    scan_mode = scan if isinstance(scan, str) else "auto"
    scan_mode = (scan_mode or "auto").strip().lower()
    if scan_mode not in {"auto", "always", "never"}:
        scan_mode = "auto"

    health = await _gw().health()

    scan_ids: set[str] = set()
    if scan_mode == "always":
        scan_ids = {hw["id"] for hw in _HARDWARE_REGISTRY}
    elif scan_mode == "auto" and _needs_live_scan(health):
        scan_ids = _unhealthy_plugin_ids(health)

    scan_skip_reason = "plugin-health compatible" if scan_mode == "auto" else "scan=never"
    skipped_owned_modbus_probe = False

    modbus_health = health.get("modbus-io")
    if isinstance(modbus_health, dict) and _modbus_health_is_no_response(modbus_health):
        # The plugin already owns the serial port. A second in-process probe can
        # report a misleading lock/access error instead of the real no-response state.
        skipped_owned_modbus_probe = "modbus-io" in scan_ids or skipped_owned_modbus_probe
        scan_ids.discard("modbus-io")
    modbus_adc_health = health.get("modbus-adc")
    if isinstance(modbus_adc_health, dict) and _modbus_health_is_no_response(modbus_adc_health):
        skipped_owned_modbus_probe = "modbus-adc" in scan_ids or skipped_owned_modbus_probe
        scan_ids.discard("modbus-adc")

    if skipped_owned_modbus_probe:
        scan_skip_reason = "plugin owns Modbus serial port; skipped duplicate no-response probe"

    should_scan = bool(scan_ids)
    if should_scan:
        probes_task = asyncio.to_thread(_probe_selected_hardware, scan_ids)
        diagnostics_task = asyncio.to_thread(_collect_hardware_diagnostics)
        probes, diagnostics = await asyncio.gather(probes_task, diagnostics_task)
    else:
        probes = {}
        diagnostics = {
            "scan_skipped": True,
            "scan_skip_reason": scan_skip_reason,
        }

    adapters = []
    for hw in _HARDWARE_REGISTRY:
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
            # For modbus-io: adapter present but module may not respond
            if hw_id in {"modbus-io", "modbus-adc"} and not probe.get("modbus_device_responds", True):
                entry["status"] = "adapter-only"
            else:
                entry["status"] = "ok"
        elif probe.get("reason"):
            entry["status"] = "no-access"
        else:
            entry["status"] = "offline"

        adapters.append(entry)

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


@router.post("/lung/stop")
async def stop_lung():
    """Emergency stop the artificial lung motor."""
    ok = await _gw().stop_lung()
    return {"ok": ok, "status": "stopped"}


@router.post("/lung/disable")
async def disable_lung():
    """De-energize the artificial lung motor (release coils)."""
    ok = await _gw().disable_lung()
    return {"ok": ok, "status": "de-energized"}


@router.get("/artificial-lung/status")
async def artificial_lung_status():
    """Logical lung state merged with motor connectivity hints."""
    return await get_artificial_lung_status(_gw())


@router.post("/artificial-lung/command")
async def artificial_lung_command(payload: dict[str, Any] = Body(default_factory=dict)):
    """Execute artificial-lung logical commands (set_lpm, lung_*, emergency_stop)."""
    command = str(payload.get("command") or "").strip()
    if not command:
        raise HTTPException(status_code=400, detail="command is required")
    args = payload.get("args")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise HTTPException(status_code=400, detail="args must be an object")
    return await execute_artificial_lung_command(command, args, _gw())


@router.get("/rtc/status")
async def rtc_status():
    """Return runtime status for the RTC sidecar."""
    return await asyncio.to_thread(build_rtc_peripheral_status)


@router.post("/rtc/command")
async def rtc_command(payload: dict[str, Any] = Body(default_factory=dict)):
    """Execute a diagnostic command against the RTC sidecar."""
    command = str(payload.get("command") or "").strip()
    if not command:
        raise HTTPException(status_code=400, detail="command is required")
    args = payload.get("args")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise HTTPException(status_code=400, detail="args must be an object")
    return await asyncio.to_thread(run_rtc_command, command, args)
