"""Regression tests for Modbus preflight soft-error reporting."""

from __future__ import annotations

from oqlos.api import hardware_probe as probe


def test_modbus_preflight_report_annotates_exception_with_public_code(monkeypatch):
    class _Gateway:
        def modbus_preflight_report(self):
            raise RuntimeError("preflight boom")

    monkeypatch.setattr(probe, "try_get_hardware_gateway", lambda: _Gateway())

    report = probe._modbus_preflight_report()
    assert report["ok"] is False
    assert report["issues"][0]["code"] == "modbus_preflight_exception"
    assert report["issues"][0]["public_code"] == "C2004-HW-0012"
    assert report["diagnostics"]["code"] == "C2004-HW-0012"
    assert report["diagnostics"]["issue_code"] == "modbus_preflight_exception"
