"""Host sidecar lifecycle for motor-dri0050 (OqlOS runs on the host)."""

from __future__ import annotations

import asyncio
import glob
import os
import shutil
from pathlib import Path
from typing import Any

import httpx

DRI0050_UNIT = "dri0050-motor-api"
DRI0050_HEALTH_URL = os.environ.get("DRI0050_URL", "http://127.0.0.1:8203").rstrip("/") + "/health"
_DRI0050_API_PORT = 8203

TIC249_UNIT = "hw-tic249"
_TIC249_BASE_URL = os.environ.get("TIC249_URL", "http://127.0.0.1:8205").rstrip("/")
TIC249_STATUS_URL = _TIC249_BASE_URL + "/api/status"
TIC249_CONNECT_URL = _TIC249_BASE_URL + "/api/connect"


def _modbus_serial_candidates() -> set[str]:
    """Ports already used by Modbus plugins — do not assign to DRI0050 pump."""
    out: set[str] = set()
    for key in (
        "MODBUS_SERIAL_PORT",
        "OQLOS_MODBUS_SERIAL_PORT",
        "MODBUS_BUS_SERIAL_PORT",
        "OQLOS_MODBUS_BUS_SERIAL_PORT",
        "MODBUS_ADC_SERIAL_PORT",
        "OQLOS_MODBUS_ADC_SERIAL_PORT",
        "MODBUS_IO_SERIAL_PORT",
        "OQLOS_MODBUS_IO_SERIAL_PORT",
    ):
        raw = os.environ.get(key, "").strip()
        if not raw:
            continue
        out.add(raw)
        try:
            out.add(os.path.realpath(raw))
        except OSError:
            pass
    return out


def resolve_dri0050_serial(configured: str = "") -> str:
    """Pick pump USB-serial: env, stable by-id, then ttyUSB not used by Modbus."""
    configured = (configured or "").strip()
    if configured and Path(configured).exists():
        return configured

    modbus_ports = _modbus_serial_candidates()
    by_id_patterns = (
        "/dev/serial/by-id/usb-1a86_USB2.0-Serial*",
        "/dev/serial/by-id/usb-1a86_*Serial*",
        "/dev/serial/by-id/*USB2.0-Serial*",
    )
    for pattern in by_id_patterns:
        for path in sorted(glob.glob(pattern)):
            try:
                if os.path.realpath(path) in modbus_ports:
                    continue
            except OSError:
                pass
            if Path(path).exists():
                return path

    for tty in sorted(glob.glob("/dev/ttyUSB*")) + sorted(glob.glob("/dev/ttyACM*")):
        try:
            if os.path.realpath(tty) in modbus_ports:
                continue
        except OSError:
            pass
        if Path(tty).exists():
            return tty

    return configured


def _dri0050_paths() -> tuple[Path, Path, str, str]:
    repo_root = Path(
        os.environ.get("DRI0050_DIR")
        or os.environ.get("OQLOS_DRI0050_DIR")
        or Path(os.environ.get("C2004_ROOT", "/home/tom/github/maskservice/c2004")).parent / "rpi-motor-DRI0050",
    ).resolve()
    python = Path(
        os.environ.get("DRI0050_PYTHON")
        or os.environ.get("OQLOS_DRI0050_PYTHON")
        or repo_root / ".venv/bin/python",
    )
    configured = (
        os.environ.get("DRI0050_PORT")
        or os.environ.get("OQLOS_DRI0050_SERIAL_PORT")
        or "/dev/serial/by-id/usb-1a86_USB2.0-Serial-if00-port0"
    ).strip()
    serial = resolve_dri0050_serial(configured)
    freq = str(os.environ.get("DRI0050_FREQ") or os.environ.get("OQLOS_DRI0050_FREQ") or "1000")
    return repo_root, python, serial, freq


async def _poll_until_ok(check, *, attempts: int, timeout: float, on_retry=None) -> bool:
    """Call `check(timeout=timeout)` up to `attempts` times, 0.25s apart.

    `on_retry(timeout=timeout)`, if given, runs after each failed check —
    e.g. to nudge a sidecar into (re)connecting before the next attempt.
    """
    for _ in range(attempts):
        if await check(timeout=timeout):
            return True
        if on_retry is not None:
            await on_retry(timeout=timeout)
        await asyncio.sleep(0.25)
    return False


async def _dri0050_probe_ok(*, timeout: float, healthy_only: bool) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(DRI0050_HEALTH_URL)
        return (not healthy_only) or resp.status_code < 300
    except (httpx.HTTPError, OSError):
        return False


async def _http_sidecar_listening(*, attempts: int = 4, timeout: float = 1.5) -> bool:
    """Sidecar process up (any HTTP response), including 503 serial I/O."""
    check = lambda *, timeout: _dri0050_probe_ok(timeout=timeout, healthy_only=False)  # noqa: E731
    return await _poll_until_ok(check, attempts=attempts, timeout=timeout)


async def _http_sidecar_healthy(*, attempts: int = 12, timeout: float = 1.5) -> bool:
    check = lambda *, timeout: _dri0050_probe_ok(timeout=timeout, healthy_only=True)  # noqa: E731
    return await _poll_until_ok(check, attempts=attempts, timeout=timeout)


async def _run_cmd(*args: str, timeout: float = 60.0) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        return 124, "", f"timed out after {timeout:g}s"
    return proc.returncode or 0, stdout.decode(), stderr.decode()


async def _free_api_port(port: int = _DRI0050_API_PORT) -> None:
    """Stop stale dri0050 listeners so systemd-run can bind :8203."""
    if shutil.which("fuser"):
        await _run_cmd("fuser", "-k", f"{port}/tcp", timeout=10.0)
    if shutil.which("lsof"):
        rc, out, _err = await _run_cmd("lsof", "-ti", f":{port}", timeout=10.0)
        if rc == 0 and out.strip():
            for pid in out.split():
                pid = pid.strip()
                if pid.isdigit():
                    await _run_cmd("kill", "-TERM", pid, timeout=5.0)
            await asyncio.sleep(0.3)


async def ensure_dri0050_sidecar(*, force_restart: bool = False) -> dict[str, Any]:
    """Start or restart dri0050-motor-api via systemd-run (same as make hardware-up)."""
    repo_root, python, serial, freq = _dri0050_paths()
    if not python.is_file():
        return {
            "ok": False,
            "step": "ensure-dri0050-sidecar",
            "error": f"DRI0050 Python not found: {python}",
        }
    if not serial or not Path(serial).exists():
        return {
            "ok": False,
            "step": "ensure-dri0050-sidecar",
            "error": f"DRI0050 serial device missing: {serial or '(none)'}",
            "hint": "Podłącz USB pompy (CH340 usb-1a86) i sprawdź ls -l /dev/serial/by-id.",
        }

    listening_unhealthy = False
    if not force_restart:
        if await _http_sidecar_healthy(attempts=4):
            return {"ok": True, "step": "ensure-dri0050-sidecar", "method": "already-healthy"}
        listening_unhealthy = await _http_sidecar_listening(attempts=2)
        if listening_unhealthy:
            force_restart = True

    if not shutil.which("systemd-run"):
        hint = "Sidecar :8203 bez poprawnego /health (503) — wymaga restartu."
        if listening_unhealthy:
            return {
                "ok": False,
                "step": "ensure-dri0050-sidecar",
                "error": "systemd-run not available",
                "method": "listening-not-healthy",
                "hint": hint,
            }
        return {"ok": False, "step": "ensure-dri0050-sidecar", "error": "systemd-run not available"}

    await _free_api_port()
    await _run_cmd("systemctl", "--user", "stop", f"{DRI0050_UNIT}.service", timeout=15.0)
    await _run_cmd("systemctl", "--user", "reset-failed", f"{DRI0050_UNIT}.service", timeout=10.0)

    web_api = repo_root / "web_api.py"
    rc, out, err = await _run_cmd(
        "systemd-run",
        "--user",
        f"--unit={DRI0050_UNIT}",
        "--description=DRI0050 motor API on 8203",
        f"--working-directory={repo_root}",
        "--setenv=API_PORT=8203",
        f"--setenv=DRI0050_PORT={serial}",
        f"--setenv=DRI0050_FREQ={freq}",
        str(python),
        str(web_api),
        timeout=30.0,
    )
    healthy = await _http_sidecar_healthy(attempts=24)
    result: dict[str, Any] = {
        "ok": healthy,
        "step": "ensure-dri0050-sidecar",
        "method": "systemd-run",
        "exit_code": rc,
        "serial_port": serial,
        "stdout": out[-800:],
        "stderr": err[-800:],
        "verified": healthy,
    }
    if not healthy:
        if listening_unhealthy or await _http_sidecar_listening(attempts=2):
            result["hint"] = (
                "Sidecar nasłuchuje na :8203, ale /health zwraca 503 — "
                "sprawdź kabel/zasilanie pompy i czy port szeregowy nie jest zajęty."
            )
        else:
            result["error"] = "dri0050-motor-api nie odpowiada na :8203 po systemd-run"
    return result


async def _tic249_status(timeout: float = 1.5) -> dict[str, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(TIC249_STATUS_URL)
        if resp.status_code < 300:
            return resp.json()
    except (httpx.HTTPError, OSError, ValueError):
        pass
    return None


async def _tic249_connect(timeout: float = 2.0) -> None:
    """Ask the sidecar to (re)open its USB handle to the Pololu Tic — no motion commands."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            await client.post(TIC249_CONNECT_URL, json={})
    except (httpx.HTTPError, OSError):
        pass


async def _tic249_listening_ok(*, timeout: float) -> bool:
    return await _tic249_status(timeout=timeout) is not None


async def _tic249_connected_ok(*, timeout: float) -> bool:
    status = await _tic249_status(timeout=timeout)
    return isinstance(status, dict) and bool(status.get("connected"))


async def _http_tic249_listening(*, attempts: int = 4, timeout: float = 1.5) -> bool:
    """Sidecar process up (any HTTP response from /api/status), regardless of USB connect state."""
    return await _poll_until_ok(_tic249_listening_ok, attempts=attempts, timeout=timeout)


async def _http_tic249_connected(*, attempts: int = 12, timeout: float = 1.5) -> bool:
    """Sidecar reachable AND reports connected=true to the Pololu Tic USB device."""
    return await _poll_until_ok(
        _tic249_connected_ok, attempts=attempts, timeout=timeout, on_retry=_tic249_connect
    )


async def ensure_tic249_sidecar(*, force_restart: bool = False) -> dict[str, Any]:
    """Restart hw-tic249.service (systemd --user) and confirm the Pololu Tic reconnects.

    Mirrors ensure_dri0050_sidecar: process-lifecycle + USB-handle recovery only,
    never issues motion/energize commands to the lung motor.
    """
    if not force_restart:
        if await _http_tic249_connected(attempts=4):
            return {"ok": True, "step": "ensure-tic249-sidecar", "method": "already-connected"}
        if await _http_tic249_listening(attempts=2):
            force_restart = True

    if not shutil.which("systemctl"):
        return {"ok": False, "step": "ensure-tic249-sidecar", "error": "systemctl not available"}

    await _run_cmd("systemctl", "--user", "reset-failed", f"{TIC249_UNIT}.service", timeout=10.0)
    rc, out, err = await _run_cmd("systemctl", "--user", "restart", f"{TIC249_UNIT}.service", timeout=15.0)

    listening = await _http_tic249_listening(attempts=24)
    if not listening:
        return {
            "ok": False,
            "step": "ensure-tic249-sidecar",
            "method": "systemctl-restart",
            "exit_code": rc,
            "stdout": out[-800:],
            "stderr": err[-800:],
            "error": f"{TIC249_UNIT}.service nie odpowiada na :8205 po restarcie",
        }

    connected = await _http_tic249_connected(attempts=24)
    result: dict[str, Any] = {
        "ok": connected,
        "step": "ensure-tic249-sidecar",
        "method": "systemctl-restart",
        "exit_code": rc,
        "verified": connected,
    }
    if not connected:
        result["error"] = "Pololu Tic USB nie połączył się po restarcie hw-tic249.service"
        result["hint"] = "Sprawdź kabel USB Tic T249 (1ffb:00c9) i czy urządzenie jest zasilane."
    return result
