from __future__ import annotations

from oqlos.hardware.startup_diagnostics import _power_from_identify


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
