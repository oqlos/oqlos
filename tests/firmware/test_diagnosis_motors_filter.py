"""Regression: motor-only diagnosis filter (no FastAPI app import)."""

from oqlos.hardware.diagnosis import filter_diagnosis_dict_for_devices, resolve_recover_plugin_ids


def test_filter_diagnosis_dict_for_motors() -> None:
    payload = {
        "devices": {
            "modbus-adc": {"device_id": "modbus-adc"},
            "motor-tic249": {"device_id": "motor-tic249"},
        },
        "global_actions": [
            {"id": "global-modbus-recover", "device_id": "*"},
            {"id": "tic249-ensure-sidecar", "device_id": "motor-tic249"},
        ],
    }
    filtered = filter_diagnosis_dict_for_devices(payload, "motors")
    assert set(filtered["devices"]) == {"motor-tic249"}
    assert filtered["global_actions"] == [{"id": "tic249-ensure-sidecar", "device_id": "motor-tic249"}]


def test_resolve_recover_plugin_ids_motors() -> None:
    assert resolve_recover_plugin_ids("motors") == ("motor-dri0050", "motor-tic249")
