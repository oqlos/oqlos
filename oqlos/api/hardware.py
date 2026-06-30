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
from oqlos.api.hardware_actuators import router as hardware_actuators_router, set_pump, set_valve
from oqlos.api.hardware_lung import (
    artificial_lung_command,
    artificial_lung_status,
    command_payload as _command_payload,
    disable_lung,
    router as hardware_lung_router,
    set_lung,
    stop_lung,
)
from oqlos.api.hardware_modbus_routes import router as hardware_modbus_router
from oqlos.api.hardware_modbus_topology import (
    _apply_modbus_topology,
    _modbus_io_device_ids,
    _modbus_runtime_serial_ports,
    _modbus_topology_mode,
    _parse_csv_ints,
)
from oqlos.api.hardware_modbus_waveshare import (
    _build_waveshare_diagnose_report,
    _build_waveshare_from_plugin_health,
    _build_waveshare_serial_stale_report,
    _diagnose_shared_bus_matrix,
    _merge_unique_text_list,
    _merge_waveshare_scan_dicts,
    _modbus_health_serial_stale,
    _modbus_plugins_healthy,
    _probe_waveshare_separate,
    _probe_waveshare_shared_bus,
    _read_output_control_modes,
    _read_waveshare_adc_slave_config,
    _read_waveshare_io_slave_config,
    _resolve_waveshare_ports,
    _split_hits_by_role,
)
from oqlos.api.hardware_modbus_wizard import (
    _collect_wizard_serial_candidates,
    _modbus_wizard_plan,
    _modbus_wizard_probe_isolated,
    _modbus_wizard_program_isolated,
    _modbus_wizard_target_ids,
    _wizard_apply_uart_write,
    _wizard_build_result,
    _wizard_check_already_configured,
    _wizard_verify_config,
)
from oqlos.api.hardware_gateway import (
    get_hardware_gateway as _gw,
    set_hardware_gateway,
    try_get_hardware_gateway,
)
from oqlos.api.hardware_hui import (
    hui_actions,
    hui_al_start,
    hui_al_stop,
    hui_hold_start,
    hui_hold_stop,
    hui_shutdown,
    router as hardware_hui_router,
)
from oqlos.api.hardware_runtime import (
    hardware_diagnose,
    hardware_temperature,
    read_cpu_temperature as _read_cpu_temperature,
    read_sensor,
    read_sensors_batch,
    router as hardware_runtime_router,
)

_settings = get_settings()
from oqlos.hardware.identify_enrichment import enrich_identify_payload
from oqlos.hardware.rtc_probe import build_rtc_peripheral_status, run_rtc_command

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/hardware", tags=["hardware"])
router.include_router(hardware_hui_router)
router.include_router(hardware_runtime_router)
router.include_router(hardware_actuators_router)
router.include_router(hardware_lung_router)
router.include_router(hardware_modbus_router)


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
    gateway = try_get_hardware_gateway()
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


@router.post("/modbus/wizard/probe-isolated")


@router.post("/modbus/wizard/program-isolated")


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


@router.get("/rtc/status")
async def rtc_status():
    """Return runtime status for the RTC sidecar."""
    return await asyncio.to_thread(build_rtc_peripheral_status)


@router.post("/rtc/command")
async def rtc_command(payload: dict[str, Any] = Body(default_factory=dict)):
    """Execute a diagnostic command against the RTC sidecar."""
    command, args = _command_payload(payload)
    return await asyncio.to_thread(run_rtc_command, command, args)
