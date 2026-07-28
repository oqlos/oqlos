"""BoardNet deployment must probe the physical Waveshare IO at 4800/N/8/1, slave 1."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_boardnet_modbus_detection_uses_stable_port_and_machine_baud() -> None:
    migration = (ROOT / "redeploy/122/migration.md").read_text(encoding="utf-8")
    detection = migration.split("MB_DETECT=", 1)[1].split("ADC_ENABLED=false", 1)[0]

    assert 'glob.glob("/dev/serial/by-id/*")' in detection
    assert "baudrate=4800" in detection
    assert "IO_BAUD=4800" in detection
    assert "device_id=1" in detection
    assert "range(1, 9)" not in detection
    assert "IO_DEVICE_ID=1" in detection
    assert "IO_ENABLED=false" not in detection
    assert "io-not-present" not in detection
    assert "MB_IO_AMBIGUOUS" in detection
    assert '"$MB_IO_DEV" != "$EXPECTED_IO_DEV"' in detection


def test_boardnet_modbus_is_verified_read_only_on_every_service_start() -> None:
    migration = (ROOT / "redeploy/122/migration.md").read_text(encoding="utf-8")
    verifier = migration.split("verify-boardnet-modbus.sh << 'SH'", 1)[1].split("\nSH\n", 1)[0]
    unit = migration.split("Description=OqlOS hardware node", 1)[1].split("\nEOF", 1)[0]

    assert "rm -f /home/pi/maskservice/scripts/verify-boardnet-modbus.sh" in migration
    assert "ID_SERIAL_SHORT=${EXPECTED_SERIAL}" in verifier
    assert 'BAUD" != "4800"' in verifier
    assert 'DEVICE_ID" != "1"' in verifier
    assert "read_coils" in verifier
    assert "write_coil" not in verifier
    assert "write_register" not in verifier
    assert ") from None" in verifier
    assert "verify-boardnet-modbus.sh" in unit
    assert "/bin/bash /home/pi/maskservice/scripts/verify-boardnet-modbus.sh" in unit
    assert "diagnostics-only degraded runtime" in unit
    assert "RestartSec=10" in unit
    assert "rm -f /home/pi/.config/systemd/user/oqlos-hardware-api.service.d/99-modbus-port.conf" in migration
    assert "rm -f /home/pi/.config/systemd/user/oqlos-hardware-api.service.d/90-modbus-device-id.conf" in migration


def test_boardnet_oqlos_logging_is_bounded_and_has_one_file_writer() -> None:
    migration = (ROOT / "redeploy/122/migration.md").read_text(encoding="utf-8")
    unit = migration.split("Description=OqlOS hardware node", 1)[1].split("\nEOF", 1)[0]

    assert "Environment=OQLOS_LOG_FILE=/home/pi/maskservice/logs/oqlos-hardware-api.log" in unit
    assert "Environment=OQLOS_LOG_MAX_BYTES=10000000" in unit
    assert "Environment=OQLOS_LOG_BACKUP_COUNT=5" in unit
    assert "Environment=OQLOS_HTTP_CLIENT_LOG_LEVEL=WARNING" in unit
    assert "StandardOutput=journal" in unit
    assert "StandardError=journal" in unit
    assert "StandardOutput=append:" not in unit

    drop_in = (ROOT / "redeploy/122/oqlos-logging.conf").read_text(encoding="utf-8")
    for expected in (
        "Environment=OQLOS_LOG_FILE=/home/pi/maskservice/logs/oqlos-hardware-api.log",
        "Environment=OQLOS_LOG_MAX_BYTES=10000000",
        "Environment=OQLOS_LOG_BACKUP_COUNT=5",
        "Environment=OQLOS_HTTP_CLIENT_LOG_LEVEL=WARNING",
        "StandardOutput=journal",
        "StandardError=journal",
    ):
        assert expected in drop_in


def test_dri0050_startup_fails_closed_when_usb_identity_is_ambiguous() -> None:
    migration = (ROOT / "redeploy/122/migration.md").read_text(encoding="utf-8")
    script = migration.split("start-dri0050-motor-api.sh << 'SH'", 1)[1].split("\nSH\n", 1)[0]

    assert "ID_VENDOR_ID=1a86" in script
    assert "ID_MODEL=(USB2" in script
    assert '"${#DRI_CANDIDATES[@]}" -gt 1' in script
    assert "nie wybieram pierwszego ttyUSB" in script
    assert "for _p in /dev/ttyUSB*" in script


def test_boardnet_deploy_uses_the_c2004_pinned_oql_store() -> None:
    migration = (ROOT / "redeploy/122/migration.md").read_text(encoding="utf-8")
    step = migration.split("- id: sync_oql_scenario", 1)[1].split("\n  - id:", 1)[0]

    assert "src: /home/tom/github/maskservice/c2004/extern/scenarios/" in step
    assert "src: /home/tom/github/oqlos/oql-scenario/" not in step


def test_boardnet_base_config_matches_machine_modbus_contract() -> None:
    payload = yaml.safe_load(
        (ROOT / "redeploy/122/oqlos-hw.yaml").read_text(encoding="utf-8")
    )
    params = payload["plugins"]["modbus-io"]["connection_params"]

    assert params == {
        "serial_port": "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5958006895-if00",
        "baudrate": 4800,
        "parity": "N",
        "device_id": 1,
    }


def test_optional_map_editor_cannot_roll_back_healthy_hardware_runtime() -> None:
    migration = (ROOT / "redeploy/122/migration.md").read_text(encoding="utf-8")
    smoke = migration.split("markpact:ref assert-hw-node-healthy", 1)[1]

    assert 'elif [ "$page" = "map-editor" ]' in smoke
    assert "nie wycofuję sprawnego runtime sprzętowego" in smoke
