"""Regression: OqlOS ensures hw-tic249 sidecar via systemctl --user restart."""

from __future__ import annotations

import pytest

from oqlos.hardware.sidecar_control import ensure_tic249_sidecar


@pytest.mark.asyncio
async def test_ensure_skips_when_already_connected(monkeypatch) -> None:
    async def connected(*args, **kwargs):  # noqa: ANN002, ANN003
        return True

    monkeypatch.setattr("oqlos.hardware.sidecar_control._http_tic249_connected", connected)

    result = await ensure_tic249_sidecar()
    assert result["ok"] is True
    assert result["method"] == "already-connected"


@pytest.mark.asyncio
async def test_ensure_restarts_when_listening_but_not_connected(monkeypatch) -> None:
    connected_checks = {"n": 0}

    async def connected(*args, **kwargs):  # noqa: ANN002, ANN003
        connected_checks["n"] += 1
        return connected_checks["n"] > 1

    async def listening(*args, **kwargs):  # noqa: ANN002, ANN003
        return True

    run_calls: list[tuple[str, ...]] = []

    async def run_cmd(*args, **kwargs):  # noqa: ANN002, ANN003
        run_calls.append(tuple(args))
        return 0, "", ""

    monkeypatch.setattr("oqlos.hardware.sidecar_control._http_tic249_connected", connected)
    monkeypatch.setattr("oqlos.hardware.sidecar_control._http_tic249_listening", listening)
    monkeypatch.setattr("oqlos.hardware.sidecar_control._run_cmd", run_cmd)
    monkeypatch.setattr("oqlos.hardware.sidecar_control.shutil.which", lambda name: "/usr/bin/systemctl")

    result = await ensure_tic249_sidecar()
    assert any(args[:3] == ("systemctl", "--user", "restart") for args in run_calls)
    assert result["method"] == "systemctl-restart"
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_ensure_reports_error_when_service_never_listens(monkeypatch) -> None:
    async def never_connected(*args, **kwargs):  # noqa: ANN002, ANN003
        return False

    async def never_listening(*args, **kwargs):  # noqa: ANN002, ANN003
        return False

    async def run_cmd(*args, **kwargs):  # noqa: ANN002, ANN003
        return 0, "", ""

    monkeypatch.setattr("oqlos.hardware.sidecar_control._http_tic249_connected", never_connected)
    monkeypatch.setattr("oqlos.hardware.sidecar_control._http_tic249_listening", never_listening)
    monkeypatch.setattr("oqlos.hardware.sidecar_control._run_cmd", run_cmd)
    monkeypatch.setattr("oqlos.hardware.sidecar_control.shutil.which", lambda name: "/usr/bin/systemctl")

    result = await ensure_tic249_sidecar(force_restart=True)
    assert result["ok"] is False
    assert "nie odpowiada" in result["error"]
