"""Stable OqlOS hardware API contract constants."""

from __future__ import annotations

from oqlos.hardware.client.platform import get_default_oqlos_api_base

DEFAULT_OQLOS_API_BASE = get_default_oqlos_api_base()
TIC249_DEFAULT_TARGET_VELOCITY = 100_000

OQLOS_HARDWARE_PREFIX = "/api/v1/hardware"

BARCODE_SCANNER_ID = "barcode-scanner"

ARTIFICIAL_LUNG_IDS = frozenset({"artificial-lung", "lung", "lung-main"})

PERIPHERAL_STATUS_COMMANDS: dict[str, str] = {
    "modbus-io": "health",
    "motor-dri0050": "status",
    "motor-tic249": "status",
    "artificial-lung": "status",
    "lung": "status",
    "lung-main": "status",
    "rtc": "status",
    "modbus-adc": "read_sensor",
    "piadc": "read_sensor",
}

PERIPHERAL_STATUS_PLUGIN_ALIASES: dict[str, str] = {
    "artificial-lung": "motor-tic249",
    "lung": "motor-tic249",
    "lung-main": "motor-tic249",
}

MODBUS_ALLOWED_VALVE_IDS = frozenset(
    {
        *(f"valve-{idx}" for idx in range(1, 15)),
        "valve-nc",
        "valve-sc",
        "valve-wc",
    }
)

FALLBACK_ADAPTERS: list[dict[str, str]] = [
    {
        "id": "modbus-adc",
        "name": "Waveshare Modbus RTU Analog Input 8CH",
        "protocol": "Modbus RTU (RS485)",
    },
    {
        "id": "motor-tic249",
        "name": "Pololu Tic T249",
        "protocol": "USB + REST",
    },
    {
        "id": "motor-dri0050",
        "name": "DFRobot DRI0050",
        "protocol": "MODBUS RTU (serial)",
    },
    {
        "id": "modbus-io",
        "name": "Waveshare Modbus RTU IO 8CH",
        "protocol": "Modbus RTU (RS485)",
    },
    {
        "id": "barcode-scanner",
        "name": "Skaner kodów kreskowych",
        "protocol": "USB HID / Keyboard Wedge",
    },
]
