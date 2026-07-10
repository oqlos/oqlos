from oqlos.api.hardware_modbus_channels import _adc_channel_rows, _io_channel_rows


def test_io_channel_rows_include_do_di_and_output_modes():
    rows = _io_channel_rows(
        {
            "coils": [True, False],
            "discrete_inputs": [False, True],
            "output_mode_registers": [0, 1],
        }
    )
    ids = [row["id"] for row in rows]
    assert ids[:2] == ["DO1", "DO2"]
    assert ids[2:4] == ["DI1", "DI2"]
    assert ids[4:6] == ["OUT_MODE_1", "OUT_MODE_2"]
    assert rows[0]["write"]["type"] == "coil"
    assert rows[4]["address"] == 0x1000


def test_adc_channel_rows_include_scaled_values():
    rows = _adc_channel_rows(
        {
            "registers": [100, 200],
            "channels": {
                "ai01": {"value": 1.23, "unit": "bar"},
                "ai02": {"value": 4.56, "unit": "bar"},
            },
        },
        read_address=0,
    )
    assert rows[0]["id"] == "AI1"
    assert rows[0]["value"] == 100
    assert rows[0]["value_scaled"] == 1.23
    assert rows[0]["writable"] is False
