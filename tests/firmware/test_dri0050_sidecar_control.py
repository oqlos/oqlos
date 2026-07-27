"""Regression: OqlOS ensures dri0050 sidecar without systemctl restart unit file."""

from __future__ import annotations

import pytest

from oqlos.hardware.sidecar_control import (
    SerialIdentityAmbiguousError,
    ensure_dri0050_sidecar,
    resolve_dri0050_serial,
)


@pytest.mark.asyncio
async def test_ensure_skips_when_already_healthy(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DRI0050_DIR", str(tmp_path))
    python = tmp_path / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\n")
    python.chmod(0o755)
    serial = tmp_path / "ttyUSB0"
    serial.write_text("")
    monkeypatch.setenv("DRI0050_PORT", str(serial))

    async def healthy(*args, **kwargs):  # noqa: ANN002, ANN003
        return True

    monkeypatch.setattr("oqlos.hardware.sidecar_control._http_sidecar_healthy", healthy)

    result = await ensure_dri0050_sidecar()
    assert result["ok"] is True
    assert result["method"] == "already-healthy"


def test_resolve_dri0050_serial_prefers_existing_by_id(monkeypatch, tmp_path) -> None:
    by_id = tmp_path / "by-id"
    by_id.mkdir()
    pump = by_id / "usb-1a86_USB2.0-Serial-if00-port0"
    pump.write_text("")
    monkeypatch.setenv("MODBUS_SERIAL_PORT", str(tmp_path / "modbus"))
    (tmp_path / "modbus").write_text("")

    monkeypatch.setattr(
        "oqlos.hardware.sidecar_control.glob.glob",
        lambda pattern: [str(pump)] if "USB2.0-Serial" in pattern else [],
    )
    assert resolve_dri0050_serial("/dev/missing") == str(pump)


def test_resolve_dri0050_serial_is_independent_of_raw_tty_order(monkeypatch, tmp_path) -> None:
    pump = tmp_path / "ttyUSB9"
    modbus = tmp_path / "ttyUSB0"
    pump.write_text("")
    modbus.write_text("")
    monkeypatch.setenv("OQLOS_MODBUS_SERIAL_PORT", str(modbus))

    raw_order = [str(pump), str(modbus)]

    def fake_glob(pattern: str) -> list[str]:
        if "by-id" in pattern:
            return []
        if pattern == "/dev/ttyUSB*":
            return list(raw_order)
        return []

    monkeypatch.setattr("oqlos.hardware.sidecar_control.glob.glob", fake_glob)

    assert resolve_dri0050_serial("/dev/missing") == str(pump)
    raw_order.reverse()
    assert resolve_dri0050_serial("/dev/missing") == str(pump)


def test_resolve_dri0050_serial_fails_closed_for_multiple_unclaimed_ports(
    monkeypatch, tmp_path
) -> None:
    first = tmp_path / "ttyUSB0"
    second = tmp_path / "ttyUSB1"
    first.write_text("")
    second.write_text("")

    def fake_glob(pattern: str) -> list[str]:
        if "by-id" in pattern:
            return []
        if pattern == "/dev/ttyUSB*":
            return [str(second), str(first)]
        return []

    monkeypatch.setattr("oqlos.hardware.sidecar_control.glob.glob", fake_glob)

    with pytest.raises(SerialIdentityAmbiguousError, match="ambiguous"):
        resolve_dri0050_serial("/dev/missing")


def test_resolve_dri0050_serial_rejects_port_reserved_by_modbus(monkeypatch, tmp_path) -> None:
    shared = tmp_path / "ttyUSB0"
    shared.write_text("")
    monkeypatch.setenv("OQLOS_MODBUS_SERIAL_PORT", str(shared))

    with pytest.raises(SerialIdentityAmbiguousError, match="reserved by a Modbus"):
        resolve_dri0050_serial(str(shared))


@pytest.mark.asyncio
async def test_ensure_reports_ambiguous_serial_identity(monkeypatch) -> None:
    def ambiguous_paths():
        raise SerialIdentityAmbiguousError("two DRI0050 candidates")

    monkeypatch.setattr("oqlos.hardware.sidecar_control._dri0050_paths", ambiguous_paths)

    result = await ensure_dri0050_sidecar()

    assert result["ok"] is False
    assert result["error_code"] == "serial_identity_ambiguous"


@pytest.mark.asyncio
async def test_ensure_restarts_when_listening_returns_503(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DRI0050_DIR", str(tmp_path))
    python = tmp_path / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\n")
    python.chmod(0o755)
    serial = tmp_path / "ttyUSB0"
    serial.write_text("")
    monkeypatch.setenv("DRI0050_PORT", str(serial))

    healthy_checks = {"n": 0}

    async def healthy(*args, **kwargs):  # noqa: ANN002, ANN003
        healthy_checks["n"] += 1
        return healthy_checks["n"] > 5

    async def listening(*args, **kwargs):  # noqa: ANN002, ANN003
        return True

    run_calls: list[tuple[str, ...]] = []

    async def run_cmd(*args, **kwargs):  # noqa: ANN002, ANN003
        run_calls.append(tuple(args))
        return 0, "", ""

    monkeypatch.setattr("oqlos.hardware.sidecar_control._http_sidecar_healthy", healthy)
    monkeypatch.setattr("oqlos.hardware.sidecar_control._http_sidecar_listening", listening)
    monkeypatch.setattr("oqlos.hardware.sidecar_control._run_cmd", run_cmd)
    async def free_port() -> None:
        return None

    monkeypatch.setattr("oqlos.hardware.sidecar_control._free_api_port", free_port)
    monkeypatch.setattr("oqlos.hardware.sidecar_control.shutil.which", lambda name: "/usr/bin/systemd-run")

    result = await ensure_dri0050_sidecar()
    assert any(args[0] == "systemd-run" for args in run_calls)
    assert result["method"] == "systemd-run"
