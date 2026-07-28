from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_boardnet_routine_oqlos_install_does_not_require_package_index() -> None:
    source = (ROOT / "redeploy/122/migration.md").read_text(encoding="utf-8")

    assert "--no-build-isolation --no-deps -e packages/oqlos-models" in source
    assert "--no-build-isolation --no-deps -e ." in source
    assert "--no-build-isolation --no-deps -e /home/pi/maskservice/pimodbus" in source
    assert 'if [ "$_new_venv" = "1" ]' in source


def test_generic_pi_hardware_profile_keeps_canonical_modbus_baud() -> None:
    source = (ROOT / "redeploy/pi-hw/migration.md").read_text(encoding="utf-8")
    profile = (ROOT / "redeploy/pi-hw/oqlos-hw.yaml").read_text(encoding="utf-8")

    assert "IO_BAUD=4800" in source
    assert "baudrate=4800" in source
    assert "Environment=OQLOS_MODBUS_ADC_BAUD=4800" in source
    assert "IO_BAUD=9600" not in source
    assert "baudrate=9600" not in source
    assert profile.count("baudrate: 4800") == 2


def test_modbus_io_runtime_defaults_are_4800_n_8_1_slave_1() -> None:
    config = (ROOT / "oqlos/config.py").read_text(encoding="utf-8")
    discovery = (ROOT / "oqlos/hardware/discovery.py").read_text(encoding="utf-8")
    registry = (ROOT / "oqlos/api/hardware_registry.py").read_text(encoding="utf-8")
    runbook = (ROOT / "redeploy/122/RUNBOOK.md").read_text(encoding="utf-8")

    assert 'modbus_baud: int = Field(\n        default=4800,' in config
    assert 'modbus_device_id: int = Field(\n        default=1,' in config
    assert 'DEFAULT_MODBUS_BAUD = int(os.getenv("MODBUS_BAUD") or os.getenv("MODBUS_BUS_BAUD") or "4800")' in discovery
    assert '"default_config": "4800 baud, N-8-1, slave address 1"' in registry
    assert "Modbus-IO is configured for `4800/N/8/1`, slave ID `1`" in runbook
