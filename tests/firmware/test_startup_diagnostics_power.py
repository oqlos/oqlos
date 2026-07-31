from __future__ import annotations

from oqlos.hardware.startup_diagnostics import (
    STARTUP_AUTO_REPAIR_DEFAULT,
    _power_from_identify,
    _report_is_degraded,
)


def test_power_from_identify_reads_health_contract():
    power = {
        "status": "critical",
        "errors": [{"error_code": "C2004-HW-0014"}],
    }
    payload = {"diagnostics": {"health": {"power": power}}}

    assert _power_from_identify(payload) is power


def test_power_from_identify_rejects_invalid_shape():
    assert _power_from_identify({}) is None
    assert _power_from_identify({"diagnostics": []}) is None
    assert _power_from_identify({"diagnostics": {"health": []}}) is None


def test_startup_auto_repair_requires_explicit_opt_in():
    assert STARTUP_AUTO_REPAIR_DEFAULT is False


def test_device_mapping_error_marks_startup_report_degraded():
    assert _report_is_degraded(
        {
            "ok": False,
            "devices": {
                "modbus-io": {"status": "error"},
                "motor-tic249": {"status": "ok"},
            },
        }
    )
