"""Platform detection helpers (Raspberry Pi vs Desktop)."""

from __future__ import annotations

import os
import platform


def is_raspberry_pi() -> bool:
    """Return True when running on a Raspberry Pi."""
    arch = platform.machine().lower()
    if arch.startswith(("arm", "aarch64")):
        return True
    try:
        with open("/proc/device-tree/model", "r", encoding="utf-8") as f:
            if "raspberry pi" in f.read().lower():
                return True
    except (FileNotFoundError, PermissionError):
        pass
    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
            if "raspberry pi" in f.read().lower():
                return True
    except (FileNotFoundError, PermissionError):
        pass
    return False


def is_docker() -> bool:
    """Return True when running inside a Docker container."""
    if os.path.exists("/.dockerenv"):
        return True
    try:
        with open("/proc/1/cgroup", "r", encoding="utf-8") as f:
            content = f.read().lower()
            return any(
                marker in content for marker in ("docker", "containerd", "kubepods")
            )
    except (FileNotFoundError, PermissionError):
        pass
    return False


def get_default_oqlos_api_base() -> str:
    """Return the default OqlOS API base URL for the current platform."""
    if is_raspberry_pi():
        return "http://localhost:8202"
    if is_docker():
        return "http://host.docker.internal:8202"
    return "http://localhost:8202"
