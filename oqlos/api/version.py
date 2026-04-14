# firmware/api/version.py
"""Version endpoint for the firmware simulator."""

import sys
from pathlib import Path

_firmware_path = Path(__file__).parent.parent
_project_root = _firmware_path.parent
if str(_firmware_path) not in sys.path:
    sys.path.insert(0, str(_firmware_path))
if str(_project_root) not in sys.path:
    sys.path.append(str(_project_root))

from oqlos.config import SERVICE_NAME, SERVICE_VERSION
from oqlos.shared.version_endpoint import create_version_router

router = create_version_router(
    service_name=SERVICE_NAME,
    version=SERVICE_VERSION,
    prefix="/api/v1",
    public_endpoint="/api/v1/version",
    source="firmware/config.py",
    tags=["version"],
)
