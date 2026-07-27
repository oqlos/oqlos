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
from typing import Any

SYS_USB = "/sys/bus/usb/devices"


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

    def _vcgencmd(arg: str) -> str | None:
        try:
            r = subprocess.run(["vcgencmd", arg], capture_output=True, text=True, timeout=3)
            return r.stdout.strip() or None
        except Exception:
            return None

    out["throttled"] = _vcgencmd("get_throttled")
    out["core_volt"] = _vcgencmd("measure_volts")

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
