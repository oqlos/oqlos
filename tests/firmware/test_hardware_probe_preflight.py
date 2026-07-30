"""Regression tests for Modbus preflight soft-error reporting."""

from __future__ import annotations

import pytest

from oqlos.api import hardware_probe as probe


def test_modbus_preflight_report_annotates_exception_with_public_code(monkeypatch):
    class _Gateway:
        def modbus_preflight_report(self):
            raise RuntimeError("password=hunter2 /srv/private")

    monkeypatch.setattr(probe, "try_get_hardware_gateway", lambda: _Gateway())

    report = probe._modbus_preflight_report()
    assert report["ok"] is False
    assert report["issues"][0]["code"] == "modbus_preflight_exception"
    assert report["issues"][0]["public_code"] == "C2004-HW-0012"
    assert report["diagnostics"]["code"] == "C2004-HW-0012"
    assert report["diagnostics"]["issue_code"] == "modbus_preflight_exception"
    assert "hunter2" not in str(report)
    assert "/srv/private" not in str(report)


def test_modbus_preflight_does_not_mask_programming_error(monkeypatch):
    class _Gateway:
        def modbus_preflight_report(self):
            raise AttributeError("programming defect")

    monkeypatch.setattr(probe, "try_get_hardware_gateway", lambda: _Gateway())

    with pytest.raises(AttributeError, match="programming defect"):
        probe._modbus_preflight_report()


def test_modbus_repair_missing_dependency_is_sanitized(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name == "pimodbus.repair":
            raise ModuleNotFoundError("password=hunter2 /srv/private")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)

    report = probe._modbus_repair_guidance()

    assert report["available"] is False
    assert report["error"] == "pimodbus-repair-unavailable"
    assert report["diagnostics"]["issue_code"] == "pimodbus_unavailable"
    assert "hunter2" not in str(report)
    assert "/srv/private" not in str(report)
