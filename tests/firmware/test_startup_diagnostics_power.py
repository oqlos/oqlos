"""Power state propagation in cached startup diagnostics."""

from oqlos.hardware.startup_diagnostics import _power_from_identify


def test_power_from_identify_reads_standardized_hardware_health() -> None:
    power = {
        "status": "critical",
        "errors": [{"error_code": "C2004-HW-0014"}],
    }

    assert _power_from_identify({"diagnostics": {"health": {"power": power}}}) == power


def test_power_from_identify_returns_none_for_legacy_payload() -> None:
    assert _power_from_identify({"diagnostics": {"health": {}}}) is None
