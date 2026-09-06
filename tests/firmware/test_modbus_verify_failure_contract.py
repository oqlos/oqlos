"""Unavailable gateways expose coded failure evidence without hardware writes."""
import pytest
from oqlos.api import hardware_modbus_io_verify as verify


@pytest.mark.asyncio
async def test_unavailable_gateway_keeps_diagnostics_and_failure_identity(monkeypatch):
    monkeypatch.setattr(verify, "try_get_hardware_gateway", lambda: None)
    report = await verify.build_modbus_io_verify_report(write_safe_off=False)
    assert report["ok"] is report["success"] is False
    assert report["code"] == report["error_code"]
    assert report["component"] == "modbus-io"
    assert report["issues"] and report["repairs"] and report["steps"]
    assert report["snapshot"] is None
