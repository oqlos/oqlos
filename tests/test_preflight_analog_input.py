"""Preflight nie może blokować na wycofanym adapterze ADC.

`resolve_required_adapter` zwraca stałą `modbus-adc` dla każdego odczytu
czujnika, bo nie zna aliasów OQL. W deploymencie boardnet (.122) ten plugin
jest celowo wyłączony (`modbus-adc: enabled: false`), a wejścia analogowe
obsługuje `usb-adc-stack` — MCP2221A na USB i DFR1184 na UART. Bez tej
bramki `oqlctl run --mode execute` przerywał każdy scenariusz czytający
czujnik, mimo że odczyt działał.
"""

from __future__ import annotations

import pytest

from oqlos.tools.cql_cli.preflight import analog_input_available, check_required_adapter

SENSOR_COMMAND = "VAL 'cisnienie_nc' 'mbar'"
ADAPTERS = [
    {"id": "modbus-adc", "status": "offline"},
    {"id": "modbus-io", "status": "ok"},
]


def health(role: str | None) -> dict:
    platform = {"analog_input_driver_role": role} if role is not None else {}
    return {"mode": "real", "platform": platform, "modbus-adc": {"status": "disabled"}}


def test_usb_adc_stack_satisfies_a_sensor_read() -> None:
    assert analog_input_available("modbus-adc", health("usb-adc-stack")) is True

    ok, adapter, status = check_required_adapter(SENSOR_COMMAND, ADAPTERS, False, True,
                                                 health=health("usb-adc-stack"))
    assert ok is True
    assert adapter == "modbus-adc"
    assert status == "ok"


def test_piadc_requirement_is_also_covered() -> None:
    assert analog_input_available("piadc", health("usb-adc-stack")) is True


@pytest.mark.parametrize("role", [None, "", "disabled", "modbus-adc"])
def test_blocks_when_no_other_driver_serves_analog_input(role) -> None:
    """Brak roli, rola wyłączona albo ta sama rola = brak obejścia."""
    assert analog_input_available("modbus-adc", health(role)) is False

    ok, _, _ = check_required_adapter(SENSOR_COMMAND, ADAPTERS, False, True, health=health(role))
    assert ok is False


def test_missing_health_fails_closed() -> None:
    assert analog_input_available("modbus-adc", None) is False

    ok, _, _ = check_required_adapter(SENSOR_COMMAND, ADAPTERS, False, True, health=None)
    assert ok is False


def test_non_analog_adapters_are_untouched() -> None:
    """Zawory i silniki muszą nadal wymagać swojego adaptera."""
    assert analog_input_available("modbus-io", health("usb-adc-stack")) is False
    assert analog_input_available("motor-dri0050", health("usb-adc-stack")) is False

    ok, adapter, status = check_required_adapter("SET 'zawór 1' '1'", ADAPTERS, False, True,
                                                 health=health("usb-adc-stack"))
    assert ok is True
    assert adapter == "modbus-io"
    assert status == "ok"


def test_valve_still_blocks_when_its_adapter_is_down() -> None:
    down = [{"id": "modbus-io", "status": "offline"}]

    ok, _, _ = check_required_adapter("SET 'zawór 1' '1'", down, False, True,
                                      health=health("usb-adc-stack"))
    assert ok is False
