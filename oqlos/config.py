"""Firmware service configuration.

Shared constants used by the firmware FastAPI app and its routers.
"""

from __future__ import annotations

import os
from pathlib import Path

from oqlos.shared.release_version import resolve_release_version

SERVICE_NAME = os.getenv("SERVICE_NAME", "firmware-simulator")
SERVICE_VERSION = resolve_release_version(Path(__file__).resolve().parent)
FIRMWARE_PORT = int(os.getenv("FIRMWARE_PORT", "8202"))
