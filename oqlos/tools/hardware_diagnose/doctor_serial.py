"""Serial port ownership detection for hardware doctor."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from oqlos.tools.hardware_diagnose.discovery import UsbDevice


def extract_pids(text: str) -> list[str]:
    pids: list[str] = []
    for token in text.replace(":", " ").split():
        if token.isdigit() and token not in pids:
            pids.append(token)
    return pids


def describe_pid(pid: str) -> dict[str, str]:
    try:
        proc = subprocess.run(
            ["ps", "-p", pid, "-o", "comm=", "-o", "args="],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=1.0,
            check=False,
        )
        line = proc.stdout.strip()
    except Exception:
        line = ""
    if not line:
        return {"pid": pid, "command": "unknown"}
    parts = line.split(None, 1)
    command = parts[0]
    args = parts[1] if len(parts) > 1 else command
    return {"pid": pid, "command": command, "args": args}


def serial_port_owners(devices: list[UsbDevice]) -> dict[str, list[dict[str, str]]]:
    """Return processes currently holding detected serial devices, best effort."""
    if not shutil.which("fuser"):
        return {}

    owners: dict[str, list[dict[str, str]]] = {}
    for dev in devices:
        try:
            proc = subprocess.run(
                ["fuser", dev.device],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=1.0,
                check=False,
            )
        except Exception:
            continue

        pids = extract_pids(f"{proc.stdout}\n{proc.stderr}")
        if not pids:
            continue
        owners[dev.device] = [describe_pid(pid) for pid in pids]
    return owners


def canonical_device_path(device: str) -> str:
    from oqlos.tools.hardware_diagnose import doctor as doc

    bound = doc._canonical_device_path
    if bound is not canonical_device_path:
        return bound(device)
    try:
        return str(Path(device).resolve(strict=False))
    except Exception:
        return device


def owners_for_configured_port(
    owners: dict[str, list[dict[str, str]]],
    configured_port: str,
) -> tuple[str, list[dict[str, str]]] | tuple[None, list[dict[str, str]]]:
    if configured_port in owners:
        return configured_port, owners[configured_port]

    configured_real_path = canonical_device_path(configured_port)
    for owner_port, proc_list in owners.items():
        if canonical_device_path(owner_port) == configured_real_path:
            return owner_port, proc_list
    return None, []
