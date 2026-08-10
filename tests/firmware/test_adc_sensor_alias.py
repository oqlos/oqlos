from oqlos.hardware.client.adc import adc_sensor_alias


def test_adc_sensor_alias_maps_channel_prefixes() -> None:
    assert adc_sensor_alias("v1") == ("v1", "ai01")
    assert adc_sensor_alias("AI02") == ("v2", "ai02")
    assert adc_sensor_alias("pi1") == ("pi1", "ai01")


def test_adc_sensor_alias_maps_logical_pressure_names() -> None:
    assert adc_sensor_alias("cisnienie") == ("v1", "ai01")
    assert adc_sensor_alias("Ciśnienie maski") == ("v1", "ai01")
    assert adc_sensor_alias("cisnienie_nc") == ("v1", "ai01")
    assert adc_sensor_alias("cisnienie-sc") == ("v2", "ai02")
    assert adc_sensor_alias("cw") == ("v3", "ai03")


def test_adc_sensor_alias_strips_window_suffixes() -> None:
    assert adc_sensor_alias("pi1.min") == ("pi1", "ai01")
    assert adc_sensor_alias("PI1.max") == ("pi1", "ai01")
    assert adc_sensor_alias("ai02.avg") == ("v2", "ai02")
