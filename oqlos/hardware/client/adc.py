"""ADC sensor id normalization (public Vn vs OqlOS aiNN)."""

from __future__ import annotations

from typing import Any


def adc_sensor_alias(raw_sensor_id: Any = "v1") -> tuple[str, str]:
    sensor_id = str(raw_sensor_id or "v1").strip().lower()

    def _alias(channel: int, public_prefix: str = "v") -> tuple[str, str]:
        if 1 <= channel <= 8:
            return f"{public_prefix}{channel}", f"ai{channel:02d}"
        return sensor_id, sensor_id

    if sensor_id.startswith("v") and sensor_id[1:].isdigit():
        return _alias(int(sensor_id[1:]), "v")
    if sensor_id.startswith("vi") and sensor_id[2:].isdigit():
        return _alias(int(sensor_id[2:]), "vi")
    if sensor_id.startswith("pi") and sensor_id[2:].isdigit():
        return _alias(int(sensor_id[2:]), "pi")
    if sensor_id.startswith("ai") and sensor_id[2:].isdigit():
        return _alias(int(sensor_id[2:]), "v")
    return sensor_id, sensor_id


def normalize_adc_read_result(result: Any, requested_sensor_id: Any = "v1") -> Any:
    public_sensor_id, oqlos_sensor_id = adc_sensor_alias(requested_sensor_id)
    if not isinstance(result, dict):
        return result
    normalized = dict(result)
    normalized["sensor_id"] = public_sensor_id
    if public_sensor_id != oqlos_sensor_id:
        normalized["source_sensor_id"] = oqlos_sensor_id
    return normalized


def normalize_adc_read_all_result(result: Any) -> Any:
    if not isinstance(result, dict):
        return result
    normalized = dict(result)
    data = normalized.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("channels"), dict):
        return normalized

    source_channels = data["channels"]
    public_channels: dict[str, Any] = {}
    for source_sensor_id, reading in source_channels.items():
        public_sensor_id, oqlos_sensor_id = adc_sensor_alias(source_sensor_id)
        if isinstance(reading, dict):
            public_reading = dict(reading)
            public_reading["sensor_id"] = public_sensor_id
            if public_sensor_id != oqlos_sensor_id:
                public_reading["source_sensor_id"] = oqlos_sensor_id
        else:
            public_reading = reading
        public_channels[public_sensor_id] = public_reading

    normalized["data"] = {
        **data,
        "channels": public_channels,
        "source_channels": source_channels,
    }
    return normalized
