"""BoardNet deployment must probe the physical Waveshare IO at 4800/N/8/1."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_boardnet_modbus_detection_uses_stable_port_and_machine_baud() -> None:
    migration = (ROOT / "redeploy/122/migration.md").read_text(encoding="utf-8")
    detection = migration.split("MB_DETECT=", 1)[1].split("ADC_ENABLED=false", 1)[0]

    assert 'glob.glob("/dev/serial/by-id/*")' in detection
    assert "baudrate=4800" in detection
    assert "baudrate=9600" not in detection
    assert "IO_BAUD=4800" in detection
    assert 'IO_DEVICE_ID="${MB_IO_ID:-2}"' in detection


def test_boardnet_base_config_matches_machine_modbus_contract() -> None:
    payload = yaml.safe_load(
        (ROOT / "redeploy/122/oqlos-hw.yaml").read_text(encoding="utf-8")
    )
    params = payload["plugins"]["modbus-io"]["connection_params"]

    assert params == {
        "serial_port": "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5958006895-if00",
        "baudrate": 4800,
        "parity": "N",
        "device_id": 2,
    }
