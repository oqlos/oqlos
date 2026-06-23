"""USB + Pi diagnostics (oqlos.hardware.usb_diagnostics) and their manage verbs."""

from __future__ import annotations

import time

import pytest

from oqlos.hardware import usb_diagnostics as u
from oqlos.hardware.transport import manage_ops


def test_list_usb_devices_structure_and_no_hang():
    # Regression guard: an earlier _find_tty used a recursive `**` glob that hung
    # on sysfs symlink cycles. Enumeration must be fast and well-formed.
    t = time.time()
    devices = u.list_usb_devices()
    assert time.time() - t < 5.0, "list_usb_devices must not hang"
    assert isinstance(devices, list)
    for d in devices:
        assert {"vendor_id", "product_id", "port_path", "tty", "serial_by_id"} <= set(d)
        assert isinstance(d["tty"], list)
        assert isinstance(d["serial_by_id"], list)


def test_pi_system_diagnostics_has_expected_keys():
    r = u.pi_system_diagnostics()
    for k in ("ok", "model", "cpu_temp_c", "memory", "serial_ports", "i2c_buses", "usb_device_count"):
        assert k in r
    assert isinstance(r["serial_ports"], list)
    assert isinstance(r["usb_device_count"], int)


def test_reset_usb_device_not_found_is_clean_failure():
    r = u.reset_usb_device(vendor_id="dead", product_id="beef")
    assert r["success"] is False
    assert "not found" in r["error"].lower()


@pytest.mark.asyncio
async def test_manage_usb_list():
    r = await manage_ops.run_manage_verb("usb-list")
    assert r["ok"] is True
    assert "count" in r and isinstance(r["devices"], list)
    assert r["count"] == len(r["devices"])


@pytest.mark.asyncio
async def test_manage_pi_diagnostics():
    r = await manage_ops.run_manage_verb("pi-diagnostics")
    assert "usb_device_count" in r


@pytest.mark.asyncio
async def test_manage_usb_reset_without_id_fails_cleanly():
    r = await manage_ops.run_manage_verb("usb-reset", {})
    assert r["success"] is False


def test_usb_verbs_listed():
    verbs = manage_ops.list_manage_verbs()
    assert {"usb-list", "pi-diagnostics", "usb-reset"} <= set(verbs)
