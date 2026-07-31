"""BoardNet deploy probes the profiled Waveshare IO at 4800/N/8/1."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_boardnet_modbus_detection_uses_stable_port_and_machine_baud() -> None:
    migration = (ROOT / "redeploy/122/migration.md").read_text(encoding="utf-8")
    detection = migration.split("MB_DETECT=", 1)[1].split("ADC_ENABLED=false", 1)[0]

    assert 'glob.glob("/dev/serial/by-id/*")' in detection
    assert "baudrate=4800" in detection
    assert "IO_BAUD=4800" in detection
    assert "device_id=${BOARDNET_MODBUS_IO_DEVICE_ID}" in detection
    assert "range(1, 9)" not in detection
    assert "IO_DEVICE_ID=${BOARDNET_MODBUS_IO_DEVICE_ID}" in detection
    assert "IO_ENABLED=false" not in detection
    assert "io-not-present" not in detection
    assert "MB_IO_AMBIGUOUS" in detection
    assert '"$MB_IO_DEV" != "$EXPECTED_IO_DEV"' in detection


def test_boardnet_modbus_identity_comes_from_device_profile() -> None:
    migration = (ROOT / "redeploy/122/migration.md").read_text(encoding="utf-8")

    assert "${BOARDNET_MODBUS_IO_PORT}" in migration
    assert "${BOARDNET_MODBUS_IO_SERIAL}" in migration
    assert "${BOARDNET_MODBUS_IO_DEVICE_ID}" in migration
    assert "5958006895" not in migration


def test_boardnet_modbus_is_verified_read_only_on_every_service_start() -> None:
    migration = (ROOT / "redeploy/122/migration.md").read_text(encoding="utf-8")
    verifier = migration.split("verify-boardnet-modbus.sh << 'SH'", 1)[1].split("\nSH\n", 1)[0]
    unit = migration.split("Description=OqlOS hardware node", 1)[1].split("\nEOF", 1)[0]

    assert (
        "rm -f /home/${BOARDNET_SSH_USER}/maskservice/scripts/"
        "verify-boardnet-modbus.sh"
    ) in migration
    assert "ID_SERIAL_SHORT=${EXPECTED_SERIAL}" in verifier
    assert 'BAUD" != "4800"' in verifier
    assert 'DEVICE_ID" != "${BOARDNET_MODBUS_IO_DEVICE_ID}"' in verifier
    assert "read_coils" in verifier
    assert "write_coil" not in verifier
    assert "write_register" not in verifier
    assert ") from None" in verifier
    assert "verify-boardnet-modbus.sh" in unit
    assert (
        "/bin/bash /home/${BOARDNET_SSH_USER}/maskservice/scripts/"
        "verify-boardnet-modbus.sh"
    ) in unit
    assert "diagnostics-only degraded runtime" in unit
    assert "RestartSec=10" in unit
    assert (
        "rm -f /home/${BOARDNET_SSH_USER}/.config/systemd/user/"
        "oqlos-hardware-api.service.d/99-modbus-port.conf"
    ) in migration
    assert (
        "rm -f /home/${BOARDNET_SSH_USER}/.config/systemd/user/"
        "oqlos-hardware-api.service.d/90-modbus-device-id.conf"
    ) in migration


def test_boardnet_oqlos_logging_is_bounded_and_has_one_file_writer() -> None:
    migration = (ROOT / "redeploy/122/migration.md").read_text(encoding="utf-8")
    unit = migration.split("Description=OqlOS hardware node", 1)[1].split("\nEOF", 1)[0]

    log_environment = (
        "Environment=OQLOS_LOG_FILE=/home/${BOARDNET_SSH_USER}/"
        "maskservice/logs/oqlos-hardware-api.log"
    )
    assert log_environment in unit
    assert "Environment=OQLOS_LOG_MAX_BYTES=10000000" in unit
    assert "Environment=OQLOS_LOG_BACKUP_COUNT=5" in unit
    assert "Environment=OQLOS_HTTP_CLIENT_LOG_LEVEL=WARNING" in unit
    assert "StandardOutput=journal" in unit
    assert "StandardError=journal" in unit
    assert "StandardOutput=append:" not in unit

    drop_in = (ROOT / "redeploy/122/oqlos-logging.conf").read_text(encoding="utf-8")
    assert (
        "Environment=OQLOS_LOG_FILE=/home/pi/maskservice/logs/"
        "oqlos-hardware-api.log"
    ) in drop_in
    for expected in (
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


def test_tic249_reuses_readiness_helper_after_every_service_start() -> None:
    migration = (ROOT / "redeploy/122/migration.md").read_text(encoding="utf-8")
    unit = migration.split("Description=Maskservice Pololu Tic T249", 1)[1].split(
        "\nUNIT", 1
    )[0]

    helper = (
        "/home/${BOARDNET_SSH_USER}/maskservice/scripts/"
        "wait-hw-tic249-ready.sh"
    )
    assert f"ExecStartPost=-{helper}" in unit
    assert "systemctl --user enable hw-tic249.service" in migration
    assert "systemctl --user restart hw-tic249.service" in migration


def test_pirtc_reuses_raspberry_pi_os_gpio_backend() -> None:
    migration = (ROOT / "redeploy/122/migration.md").read_text(encoding="utf-8")
    pirtc = migration.split("markpact:ref deploy-pirtc-sidecar", 1)[1].split(
        "```", 1
    )[0]

    assert "python3 -m venv --system-site-packages .venv" in pirtc


def test_boardnet_watchdog_is_opt_in_and_has_persistent_audit() -> None:
    migration = (ROOT / "redeploy/122/migration.md").read_text(encoding="utf-8")
    pirtc = migration.split("markpact:ref deploy-pirtc-sidecar", 1)[1].split(
        "```", 1
    )[0]
    audit = migration.split(
        "markpact:ref configure-boardnet-watchdog-observability", 1
    )[1].split("```", 1)[0]

    assert "Environment=WATCHDOG_ENABLED=false" in pirtc
    assert "Environment=WATCHDOG_MODEL=disabled" in pirtc
    assert "watchdog.get(\"ready\") is True" in pirtc
    assert "watchdog_is_safely_disabled" in pirtc
    assert "for _attempt in $(seq 1 15)" in pirtc
    assert 'if [ "$WATCHDOG_SAFE" != "1" ]' in pirtc
    assert "StandardOutput=journal" in pirtc
    assert "StandardOutput=append:" not in pirtc

    assert "Storage=persistent" in audit
    assert 'WATCHDOG_ENABLED="${BOARDNET_RUNTIME_WATCHDOG_ENABLED}"' in audit
    assert 'WATCHDOG_POLICY=disabled' in audit
    assert "RuntimeWatchdogSec=3min" in audit
    assert "RebootWatchdogSec=5min" in audit
    assert "RuntimeWatchdogSec=0" in audit
    assert "RebootWatchdogSec=0" in audit
    assert "KExecWatchdogSec=0" in audit
    assert "ServiceWatchdogs=" not in audit
    assert 'internal["policy"] == "enabled"' in audit
    assert (
        'internal["policy"] != "enabled" and internal["state"] == "active"'
        in audit
    )
    assert 'RUNTIME_WATCHDOG" = "3min"' in audit
    assert 'RUNTIME_WATCHDOG" = "0"' in audit
    assert "systemctl --no-block daemon-reexec" in audit
    assert "daemon-reexec skipped" in audit
    assert "sudo systemctl daemon-reexec\n" not in audit
    assert "boardnet-watchdog-audit.timer" in audit
    assert "C2004-HW-0016" in audit
    assert "C2004-HW-0017" in audit
    assert "boot_id" in audit


def test_boardnet_deploy_uses_the_canonical_oql_scenario_store() -> None:
    migration = (ROOT / "redeploy/122/migration.md").read_text(encoding="utf-8")
    step = migration.split("- id: sync_oql_scenario", 1)[1].split("\n  - id:", 1)[0]

    assert "src: ${OQL_SCENARIOS_DIR}/" in step
    assert "src: /home/tom/github/maskservice/c2004/extern/scenarios/" not in step


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


def test_optional_map_editor_cannot_roll_back_healthy_hardware_runtime() -> None:
    migration = (ROOT / "redeploy/122/migration.md").read_text(encoding="utf-8")
    smoke = migration.split("markpact:ref assert-hw-node-healthy", 1)[1]

    assert 'elif [ "$page" = "map-editor" ]' in smoke
    assert "nie wycofuję sprawnego runtime sprzętowego" in smoke


def test_hardware_smoke_posts_json_without_appending_a_brace() -> None:
    migration = (ROOT / "redeploy/122/migration.md").read_text(encoding="utf-8")
    smoke = migration.split("markpact:ref assert-hw-node-healthy", 1)[1]

    assert 'local data="${3:-{}}"' not in smoke
    assert 'local data="${3-}"' in smoke
    assert "[ -n \"$data\" ] || data='{}'" in smoke
    assert "EXPECTED_SCENARIOS_DIR=\"${HOME}/oqlos/oql-scenario\"" in smoke


def test_usb_adc_deploy_uses_profiled_uart_and_releases_serial_console() -> None:
    migration = (ROOT / "redeploy/122/migration.md").read_text(encoding="utf-8")
    deploy = migration.split("markpact:ref deploy-usb-adc-stack", 1)[1]

    assert "python3 -c 'import lgpio'" in deploy
    assert "sudo apt-get install -y python3-lgpio" in deploy
    assert "python3 -m venv --system-site-packages" in deploy
    assert "PIP_PREFER_BINARY=1" in deploy
    assert "usb-adc-stack.service.d/20-boardnet.conf" in deploy
    assert "Environment=DFR1184_SERIAL_PORT=${BOARDNET_DFR1184_PORT}" in deploy
    assert "Environment=DFR1184_BAUDRATE=${BOARDNET_DFR1184_BAUDRATE}" in deploy
    assert "BOARDNET_DFR1184_DISABLE_SERIAL_CONSOLE" in deploy
    assert "console=serial0," in deploy


def test_mosquitto_password_is_resynced_from_runtime_env() -> None:
    migration = (ROOT / "redeploy/122/migration.md").read_text(encoding="utf-8")
    install = migration.split("markpact:ref install-mosquitto", 1)[1]

    assert "if [ ! -f /home/${BOARDNET_SSH_USER}/maskservice/config/mosquitto.passwd ]" not in install
    assert "mosquitto_passwd -b -c" in install
    assert "chmod 600 /home/${BOARDNET_SSH_USER}/maskservice/config/mosquitto.passwd" in install
