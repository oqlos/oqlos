"""Whole-board power control for the hardware node (reboot from the UI).

The hardware UI runs on the Pi itself, so a reboot kills this process too:
the reboot is detached and delayed a moment so the HTTP response can reach
the browser first.
"""

from __future__ import annotations

import logging
import pathlib
import subprocess
from typing import Any

logger = logging.getLogger(__name__)

REBOOT_DELAY_SEC = 2.0


def _in_container() -> bool:
    if pathlib.Path("/.dockerenv").exists():
        return True
    try:
        cgroup = pathlib.Path("/proc/1/cgroup").read_text(encoding="utf-8")
    except OSError:
        return False
    return "docker" in cgroup or "containerd" in cgroup


def _sudo_available() -> bool:
    try:
        result = subprocess.run(
            ["sudo", "-n", "true"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def schedule_host_reboot(*, confirm: bool) -> dict[str, Any]:
    """Reboot the whole board after a short delay. Requires confirm=True."""
    if not confirm:
        return {
            "ok": False,
            "step": "host-reboot",
            "error": "Reboot not confirmed",
            "hint": 'POST body must contain {"confirm": true}',
        }
    if _in_container():
        return {
            "ok": False,
            "step": "host-reboot",
            "error": "Refusing to reboot: running inside a container, not on the board",
        }
    if not _sudo_available():
        return {
            "ok": False,
            "step": "host-reboot",
            "error": "Passwordless sudo unavailable — cannot reboot the host",
            "hint": "Grant NOPASSWD for /usr/bin/systemctl reboot to the service user",
        }

    logger.warning("Host reboot requested from hardware UI; rebooting in %.1fs", REBOOT_DELAY_SEC)
    subprocess.Popen(
        ["/bin/sh", "-c", f"sleep {REBOOT_DELAY_SEC}; exec sudo -n systemctl reboot"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return {
        "ok": True,
        "step": "host-reboot",
        "scheduled_in_sec": REBOOT_DELAY_SEC,
        "note": "Board is rebooting; hardware services return after boot",
    }
