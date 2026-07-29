"""
oqlos.hardware.usb_diagnostics — USB + Raspberry Pi system diagnostics.

Permission-free enumeration by reading sysfs (`/sys/bus/usb/devices`), so it works
without root and without libusb string-descriptor access. Exposed to OQL-over-MQTT
via the manage verbs ``usb-list``, ``pi-diagnostics`` and ``usb-reset`` (see
:mod:`oqlos.hardware.transport.manage_ops`).

Note on "changing a USB port": a device's *physical* port cannot be reassigned in
software. What is possible — and provided here — is a driver-level **reset /
re-enumeration** (``USBDEVFS_RESET`` ioctl), which makes the kernel re-probe the
device (useful for a stuck CH340 / Tic). Stable logical naming across ports is a
udev concern, not a runtime one.
"""

from __future__ import annotations

import glob
import os
import re
import subprocess
from datetime import datetime, timezone
from typing import Any

SYS_USB = "/sys/bus/usb/devices"

_THROTTLE_FLAGS: dict[int, str] = {
    0: "undervoltage",
    1: "frequency_capped",
    2: "throttled",
    3: "soft_temperature_limit",
}


def decode_throttled(raw: str | None) -> dict[str, Any]:
    """Decode ``vcgencmd get_throttled`` into the public power contract.

    Raspberry Pi uses bits 0..3 for conditions active now and bits 16..19 for
    conditions observed since boot.  Only current undervoltage is the safety
    error C2004-HW-0014; historical flags remain warnings and never pretend
    that an alarm is active.
    """
    observed_at = datetime.now(timezone.utc).isoformat()
    match = re.search(r"(?:throttled=)?(0x[0-9a-f]+|[0-9]+)", raw or "", re.I)
    if not match:
        return {
            "available": False,
            "status": "unknown",
            "observed_at": observed_at,
            "age_ms": 0,
            "source": "vcgencmd.get_throttled",
            "raw": raw,
            "mask": None,
            "active": [],
            "historical": [],
            "active_flags": [],
            "historical_flags": [],
            "errors": [],
            "warnings": [
                {
                    "issue_code": "boardnet_power_telemetry_unavailable",
                    "severity": "warning",
                    "message": "Raspberry Pi power telemetry is unavailable",
                }
            ],
        }

    token = match.group(1)
    mask = int(token, 16 if token.lower().startswith("0x") else 10)
    active = [name for bit, name in _THROTTLE_FLAGS.items() if mask & (1 << bit)]
    historical = [
        name for bit, name in _THROTTLE_FLAGS.items() if mask & (1 << (bit + 16))
    ]
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if "undervoltage" in active:
        errors.append(
            {
                "error_code": "C2004-HW-0014",
                "issue_code": "boardnet_undervoltage_active",
                "domain": "hardware",
                "severity": "critical",
                "retryable": False,
                "architecture": "SOA",
                "component": "boardnet-power",
                "stage": "adapter.health",
                "message": "BoardNet reports active Raspberry Pi supply undervoltage",
            }
        )
    for flag in active:
        if flag == "undervoltage":
            continue
        warnings.append(
            {
                "issue_code": "boardnet_power_condition_active",
                "condition": flag,
                "severity": "warning",
                "message": f"Raspberry Pi reports active {flag.replace('_', ' ')}",
            }
        )
    for flag in historical:
        warnings.append(
            {
                "issue_code": "boardnet_power_condition_historical",
                "condition": flag,
                "severity": "warning",
                "message": f"Raspberry Pi reported {flag.replace('_', ' ')} since boot",
            }
        )

    status = "critical" if errors else "warning" if warnings else "ok"
    return {
        "available": True,
        "status": status,
        "observed_at": observed_at,
        "age_ms": 0,
        "source": "vcgencmd.get_throttled",
        "raw": raw,
        "mask": mask,
        "mask_hex": f"0x{mask:x}",
        "active": active,
        "historical": historical,
        "active_flags": active,
        "historical_flags": historical,
        "errors": errors,
        "warnings": warnings,
    }


def _vcgencmd(arg: str) -> str | None:
    try:
        result = subprocess.run(
            ["vcgencmd", arg], capture_output=True, text=True, timeout=3, check=False
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def pi_power_diagnostics() -> dict[str, Any]:
    """Return the standardized Raspberry Pi power snapshot."""
    result = decode_throttled(_vcgencmd("get_throttled"))
    # This is SoC core voltage, not the 5 V input and not a power measurement.
    result["core_voltage_raw"] = _vcgencmd("measure_volts")
    result["input_power_measurement_available"] = False
    return result


def _read(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except Exception:
        return None


def _find_tty(dev_dir: str) -> list[str]:
    """Find /dev/ttyUSB*|ttyACM* nodes owned by THIS device's interfaces.

    Only inspects the device's own interface dirs (named ``<dev>:<cfg>.<intf>``,
    containing a colon) — never child USB device dirs — so a hub is not credited
    with a downstream device's tty. Uses bounded, NON-recursive globs: tty nodes
    sit at ``<iface>/ttyUSB0`` (usb-serial) or ``<iface>/tty/ttyACM0`` (cdc-acm).
    A recursive ``**`` glob must NOT be used here — sysfs symlink cycles make it
    hang on a Pi.
    """
    found: set[str] = set()
    for iface in glob.glob(os.path.join(dev_dir, "*:*")):
        candidates = (
            glob.glob(os.path.join(iface, "ttyUSB*"))
            + glob.glob(os.path.join(iface, "ttyACM*"))
            + glob.glob(os.path.join(iface, "tty", "ttyUSB*"))
            + glob.glob(os.path.join(iface, "tty", "ttyACM*"))
        )
        for ttypath in candidates:
            name = os.path.basename(ttypath)
            if name.startswith(("ttyUSB", "ttyACM")) and os.path.exists(f"/dev/{name}"):
                found.add(f"/dev/{name}")
    return sorted(found)


def _find_drivers(dev_dir: str) -> list[str]:
    """Return kernel drivers bound to this USB device's interfaces."""
    found: set[str] = set()
    for iface in glob.glob(os.path.join(dev_dir, "*:*")):
        driver = os.path.join(iface, "driver")
        try:
            if os.path.islink(driver):
                found.add(os.path.basename(os.path.realpath(driver)))
        except OSError:
            continue
    return sorted(found)


def list_usb_devices() -> list[dict[str, Any]]:
    """Enumerate connected USB devices (sysfs; no root needed)."""
    devices: list[dict[str, Any]] = []
    if not os.path.isdir(SYS_USB):
        return devices  # non-Linux host

    # Pre-map /dev/serial/by-id -> real tty for serial_by_id annotation.
    byid: dict[str, list[str]] = {}
    for link in glob.glob("/dev/serial/by-id/*"):
        try:
            byid.setdefault(os.path.realpath(link), []).append(link)
        except Exception:
            pass

    for entry in sorted(os.listdir(SYS_USB)):
        if ":" in entry:  # an interface (e.g. 1-1.5:1.0), not a device
            continue
        d = os.path.join(SYS_USB, entry)
        vid = _read(os.path.join(d, "idVendor"))
        if not vid:  # usb controllers (usb1, ...) have no idVendor
            continue
        busnum = _read(os.path.join(d, "busnum"))
        devnum = _read(os.path.join(d, "devnum"))
        tty = _find_tty(d)
        dev_node = None
        if busnum and devnum and busnum.isdigit() and devnum.isdigit():
            dev_node = f"/dev/bus/usb/{int(busnum):03d}/{int(devnum):03d}"
        dev = {
            "id": entry,
            "vendor_id": vid,
            "product_id": _read(os.path.join(d, "idProduct")),
            "vendor": _read(os.path.join(d, "manufacturer")),
            "product": _read(os.path.join(d, "product")),
            "serial": _read(os.path.join(d, "serial")),
            "bus": busnum,
            "device": devnum,
            "port_path": entry,  # e.g. 1-1.5 — the physical topology path
            "speed_mbps": _read(os.path.join(d, "speed")),
            "dev_node": dev_node,
            "tty": tty,
            "drivers": _find_drivers(d),
            "serial_by_id": sorted(
                {link for t in tty for link in byid.get(os.path.realpath(t), [])}
            ),
        }
        devices.append(dev)
    return devices


_KERNEL_EVENT_RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("undervoltage", "error", re.compile(r"under.?voltage detected", re.I)),
    ("voltage_normalized", "info", re.compile(r"voltage normali[sz]ed", re.I)),
    (
        "usb_host_timeout",
        "error",
        re.compile(r"dwc_otg_hcd_urb_dequeue|timed out waiting for FSM .*transfer", re.I),
    ),
    ("usb_disconnect", "error", re.compile(r"usb\s+[\w.:-]+:.*disconnect", re.I)),
    ("usb_reset", "warn", re.compile(r"usb\s+[\w.:-]+:.*reset (?:full|high|super)-speed", re.I)),
    (
        "serial_driver",
        "info",
        re.compile(r"tty(?:ACM|USB)\d+|cdc_acm|ch34[13]|ch343", re.I),
    ),
)


def _kernel_event_snapshot(limit: int = 60) -> dict[str, Any]:
    """Return a bounded, categorized kernel log view relevant to BoardNet I/O.

    The endpoint deliberately does not expose arbitrary dmesg output.  It keeps
    only power, USB-host and serial-driver lines needed to diagnose hardware
    availability from the browser.
    """
    try:
        result = subprocess.run(
            ["dmesg", "--ctime", "--color=never"],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "error": str(exc), "counts": {}, "events": []}

    if result.returncode != 0:
        return {
            "available": False,
            "error": result.stderr.strip() or f"dmesg exited {result.returncode}",
            "counts": {},
            "events": [],
        }

    counts = {kind: 0 for kind, _level, _pattern in _KERNEL_EVENT_RULES}
    events: list[dict[str, str]] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for kind, level, pattern in _KERNEL_EVENT_RULES:
            if not pattern.search(line):
                continue
            counts[kind] += 1
            events.append({"kind": kind, "level": level, "message": line})
            break

    bounded = max(1, min(int(limit), 200))
    return {
        "available": True,
        "error": None,
        "counts": counts,
        "events": events[-bounded:],
    }


def pi_system_diagnostics() -> dict[str, Any]:
    """Raspberry Pi health snapshot: model, temp, throttling, memory, uptime, ports."""
    out: dict[str, Any] = {"ok": True}
    out["model"] = (_read("/proc/device-tree/model") or "").replace("\x00", "") or None
    out["boot_id"] = _read("/proc/sys/kernel/random/boot_id")
    out["kernel_release"] = os.uname().release if hasattr(os, "uname") else None

    temp = _read("/sys/class/thermal/thermal_zone0/temp")
    out["cpu_temp_c"] = round(int(temp) / 1000, 1) if temp and temp.lstrip("-").isdigit() else None

    out["throttled"] = _vcgencmd("get_throttled")
    out["core_volt"] = _vcgencmd("measure_volts")
    out["power"] = decode_throttled(out["throttled"])
    out["power"]["core_voltage_raw"] = out["core_volt"]
    out["power"]["input_power_measurement_available"] = False
    out["overall_status"] = out["power"]["status"]
    out["errors"] = list(out["power"]["errors"])
    out["warnings"] = list(out["power"]["warnings"])
    out["ok"] = not bool(out["errors"])

    mem: dict[str, str] = {}
    for line in (_read("/proc/meminfo") or "").splitlines():
        if line.split(":")[0] in ("MemTotal", "MemFree", "MemAvailable"):
            k, _, v = line.partition(":")
            mem[k.strip()] = v.strip()
    out["memory"] = mem

    up = _read("/proc/uptime")
    out["uptime_s"] = float(up.split()[0]) if up else None
    out["loadavg"] = _read("/proc/loadavg")
    out["serial_ports"] = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
    out["i2c_buses"] = sorted(glob.glob("/dev/i2c-*"))
    out["usb_device_count"] = len(list_usb_devices())
    kernel = _kernel_event_snapshot()
    out["kernel_events_available"] = kernel["available"]
    out["kernel_events_error"] = kernel["error"]
    out["kernel_event_counts"] = kernel["counts"]
    out["kernel_events"] = kernel["events"]
    return out


# USBDEVFS_RESET = _IO('U', 20) -> (ord('U') << 8) | 20
_USBDEVFS_RESET = (ord("U") << 8) | 20


def reset_usb_device(
    vendor_id: str | None = None,
    product_id: str | None = None,
    dev_node: str | None = None,
) -> dict[str, Any]:
    """Driver-level reset / re-enumeration of a USB device (needs root or udev rw).

    Resolves the device node by vendor/product id if ``dev_node`` is not given.
    This does NOT change the physical port — it makes the kernel re-probe the device.
    """
    import fcntl

    target = dev_node
    matched = None
    if not target:
        for d in list_usb_devices():
            if vendor_id and d["vendor_id"] != vendor_id:
                continue
            if product_id and d["product_id"] != product_id:
                continue
            if vendor_id or product_id:
                target = d["dev_node"]
                matched = d
                break
    if not target:
        return {"success": False, "error": "USB device not found for the given vendor/product id"}
    try:
        fd = os.open(target, os.O_WRONLY)
        try:
            fcntl.ioctl(fd, _USBDEVFS_RESET, 0)
        finally:
            os.close(fd)
        return {"success": True, "reset": target, "device": matched}
    except PermissionError as exc:
        return {
            "success": False,
            "error": f"permission denied on {target} — needs root or a udev rule (MODE 0666) for this device",
            "detail": str(exc),
        }
    except Exception as exc:
        return {"success": False, "error": str(exc), "target": target}
