from oqlos.hardware.plugins.modbus_adc import _resolve_channel


def test_resolve_channel_accepts_map_editor_v_inputs() -> None:
    assert _resolve_channel("v1") == 0
    assert _resolve_channel("V2") == 1
    assert _resolve_channel("vi3") == 2
    assert _resolve_channel("PI1") == 0
