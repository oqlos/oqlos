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
        assert {"vendor_id", "product_id", "port_path", "tty", "drivers", "serial_by_id"} <= set(d)
        assert isinstance(d["tty"], list)
        assert isinstance(d["drivers"], list)
        assert isinstance(d["serial_by_id"], list)


def test_pi_system_diagnostics_has_expected_keys():
    r = u.pi_system_diagnostics()
    for k in (
        "ok", "model", "boot_id", "kernel_release", "cpu_temp_c", "memory",
        "serial_ports", "i2c_buses", "usb_device_count", "kernel_event_counts", "kernel_events",
        "power", "overall_status", "errors", "warnings",
    ):
        assert k in r
    assert isinstance(r["serial_ports"], list)
    assert isinstance(r["usb_device_count"], int)


@pytest.mark.parametrize(
    ("raw", "status", "active", "historical", "error_codes"),
    [
        ("throttled=0x0", "ok", [], [], []),
        (
            "throttled=0x1",
            "critical",
            ["undervoltage"],
            [],
            ["C2004-HW-0014"],
        ),
        (
            "throttled=0x10000",
            "warning",
            [],
            ["undervoltage"],
            [],
        ),
        (
            "throttled=0x10001",
            "critical",
            ["undervoltage"],
            ["undervoltage"],
            ["C2004-HW-0014"],
        ),
    ],
)
def test_decode_throttled_contract(raw, status, active, historical, error_codes):
    result = u.decode_throttled(raw)

    assert result["available"] is True
    assert result["status"] == status
    assert result["active_flags"] == active
    assert result["historical_flags"] == historical
    assert [item["error_code"] for item in result["errors"]] == error_codes


def test_decode_throttled_does_not_confuse_throttling_with_undervoltage():
    result = u.decode_throttled("throttled=0x40004")

    assert result["status"] == "warning"
    assert result["active_flags"] == ["throttled"]
    assert result["historical_flags"] == ["throttled"]
    assert result["errors"] == []


def test_active_undervoltage_error_uses_shared_soa_contract():
    error = u.decode_throttled("throttled=0x1")["errors"][0]

    assert error == {
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


def test_decode_throttled_unavailable_is_explicit():
    result = u.decode_throttled(None)

    assert result["available"] is False
    assert result["status"] == "unknown"
    assert result["errors"] == []
    assert result["warnings"][0]["issue_code"] == "boardnet_power_telemetry_unavailable"


def test_kernel_event_snapshot_is_bounded_and_categorized(monkeypatch):
    class Result:
        returncode = 0
        stderr = ""
        stdout = "\n".join([
            "[boot] cdc_acm 1-1.4:1.0: ttyACM0: USB ACM device",
            "[power] hwmon: Undervoltage detected!",
            "[usb] WARN::dwc_otg_hcd_urb_dequeue: Timed out waiting for FSM NP transfer",
            "[power] hwmon: Voltage normalised",
        ])

    monkeypatch.setattr(u.subprocess, "run", lambda *_args, **_kwargs: Result())

    snapshot = u._kernel_event_snapshot(limit=2)

    assert snapshot["available"] is True
    assert snapshot["counts"]["undervoltage"] == 1
    assert snapshot["counts"]["usb_host_timeout"] == 1
    assert len(snapshot["events"]) == 2
    assert snapshot["events"][-1]["kind"] == "voltage_normalized"


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
