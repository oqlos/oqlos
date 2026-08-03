from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from oqlos.api.main import app
from oqlos.hardware.configuration import (
    HardwareConfigurationError,
    load_hardware_configuration,
    parse_hardware_configuration,
    resolve_effective_hardware_configuration,
    save_hardware_configuration,
    serialize_hardware_configuration,
)


FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "hardware-configuration"


def test_oql_yaml_json_have_identical_complete_semantics() -> None:
    documents = {
        format: load_hardware_configuration(FIXTURES / f"boardnet.{format}", allow_legacy=False)
        for format in ("oql", "yaml", "json")
    }
    assert documents["oql"] == documents["yaml"] == documents["json"]
    config = documents["yaml"]
    assert config.plugins["modbus-io"].connection_params["device_id"] == 2
    assert config.aliases["cisnienie_nc"].conversion["adc_per_volt"] == 3950
    assert config.processes["measurement.sensors.read"].poll_interval_ms == 100
    assert config.profiles["hui"]["holds"]["head-inflate"]["pump_pct"] == 70
    assert config.secret_refs["mqttPassword"].key == "OQLOS_OQL_MQTT_PASSWORD"


@pytest.mark.parametrize("source_format", ["oql", "yaml", "json"])
@pytest.mark.parametrize("target_format", ["oql", "yaml", "json"])
def test_every_format_pair_round_trips(source_format: str, target_format: str) -> None:
    source = load_hardware_configuration(FIXTURES / f"boardnet.{source_format}", allow_legacy=False)
    converted = serialize_hardware_configuration(source, target_format)
    assert parse_hardware_configuration(converted, target_format) == source


def test_unknown_top_level_field_is_rejected() -> None:
    with pytest.raises(HardwareConfigurationError) as caught:
        parse_hardware_configuration(
            json.dumps({"schemaVersion": "hardware-configuration-v1", "plugnis": {}}),
            "json",
        )
    assert caught.value.issues[0]["field"] == "plugnis"


@pytest.mark.parametrize("format", ["oql", "yaml", "json"])
def test_motor2_runtime_constraints_are_identical_in_every_format(format: str) -> None:
    config = load_hardware_configuration(FIXTURES / "boardnet.yaml", allow_legacy=False)
    data = config.canonical_dict()
    data["runtime"]["motor2"]["maxStepsPerSecond"] = 500
    data["runtime"]["motor2"]["defaultSpeedStepsPerSecond"] = 501
    if format == "json":
        content = json.dumps(data)
    elif format == "yaml":
        content = yaml.safe_dump(data, sort_keys=False)
    else:
        content = serialize_hardware_configuration(config, "oql")
        compact = json.dumps(data["runtime"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        runtime_line = f"  SET 'hardware.configuration.runtime' {json.dumps(compact, ensure_ascii=False)}"
        content = "\n".join(
            runtime_line if line.startswith("  SET 'hardware.configuration.runtime'") else line
            for line in content.splitlines()
        )
    with pytest.raises(HardwareConfigurationError, match="defaultSpeedStepsPerSecond"):
        parse_hardware_configuration(content, format)


def test_motor2_idle_policy_is_explicit_and_type_checked() -> None:
    config = load_hardware_configuration(FIXTURES / "boardnet.oql", allow_legacy=False)

    assert config.runtime["motor2"]["idleState"] == "deenergized"
    assert config.runtime["motor2"]["deenergizeOnStop"] is True
    assert config.runtime["motor2"]["deenergizeOnStartup"] is True

    invalid = config.canonical_dict()
    invalid["runtime"]["motor2"]["deenergizeOnStop"] = "true"
    with pytest.raises(HardwareConfigurationError, match="deenergizeOnStop must be a boolean"):
        parse_hardware_configuration(json.dumps(invalid), "json")


def test_inline_secret_is_rejected_but_reference_is_allowed() -> None:
    with pytest.raises(HardwareConfigurationError, match="inline secret"):
        parse_hardware_configuration(
            json.dumps({
                "schemaVersion": "hardware-configuration-v1",
                "runtime": {"mqtt_password": "plain-text"},
            }),
            "json",
        )
    valid = parse_hardware_configuration(
        json.dumps({
            "schemaVersion": "hardware-configuration-v1",
            "secretRefs": {"mqtt": {"provider": "env", "key": "OQLOS_MQTT_PASSWORD"}},
        }),
        "json",
    )
    assert valid.secret_refs["mqtt"].provider == "env"


def test_legacy_map_migrates_once_without_runtime_fallback() -> None:
    migrated = parse_hardware_configuration(
        """
runtimeConfig:
  motor2: {strokeSteps: 1000}
objectActionMap:
  pump: {on: pump.start}
paramSensorMap:
  PI1: {sensor: AI01}
funcImplementations:
  smoke: {steps: []}
""",
        "yaml",
        allow_legacy=True,
    )
    assert migrated.runtime["motor2"]["strokeSteps"] == 1000
    assert migrated.actions["objects"]["pump"]["on"] == "pump.start"
    assert migrated.sensors["bindings"]["PI1"]["sensor"] == "AI01"
    assert migrated.functions["smoke"]["steps"] == []


def test_effective_configuration_explains_environment_override() -> None:
    configured = load_hardware_configuration(FIXTURES / "boardnet.yaml", allow_legacy=False)
    effective, overrides = resolve_effective_hardware_configuration(
        configured,
        {"OQLOS_MODBUS_SERIAL_PORT": "/dev/serial/by-id/runtime-io"},
    )
    assert configured.plugins["modbus-io"].connection_params["serial_port"] == "/dev/serial/by-id/usb-boardnet-io"
    assert effective.plugins["modbus-io"].connection_params["serial_port"] == "/dev/serial/by-id/runtime-io"
    assert overrides == [{
        "path": "plugins.modbus-io.connection_params.serial_port",
        "source": "OQLOS_MODBUS_SERIAL_PORT",
        "configured": "/dev/serial/by-id/usb-boardnet-io",
        "effective": "/dev/serial/by-id/runtime-io",
    }]


def test_effective_configuration_reuses_parse_until_source_changes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from oqlos.hardware import configuration as configuration_module

    source = FIXTURES / "boardnet.yaml"
    target = tmp_path / "oqlos.yaml"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    configuration_module._load_effective_hardware_configuration_cached.cache_clear()
    original_loader = configuration_module.load_hardware_configuration
    calls: list[Path] = []

    def counted_loader(path, *, allow_legacy=False):
        calls.append(Path(path))
        return original_loader(path, allow_legacy=allow_legacy)

    monkeypatch.setattr(configuration_module, "load_hardware_configuration", counted_loader)

    first, _ = configuration_module.load_effective_hardware_configuration(target)
    second, _ = configuration_module.load_effective_hardware_configuration(target)

    assert first is second
    assert calls == [target.resolve()]


def test_atomic_save_leaves_no_temporary_file(tmp_path: Path) -> None:
    config = load_hardware_configuration(FIXTURES / "boardnet.yaml", allow_legacy=False)
    target = tmp_path / "oqlos.json"
    save_hardware_configuration(target, config)
    assert load_hardware_configuration(target, allow_legacy=False) == config
    assert list(tmp_path.glob(".oqlos.json.*")) == []


def test_configuration_api_and_legacy_routes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = FIXTURES / "boardnet.yaml"
    target = tmp_path / "oqlos.yaml"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("OQLOS_CONFIG_PATH", str(target))
    client = TestClient(app)

    response = client.get("/api/v3/hardware/configuration")
    assert response.status_code == 200
    assert response.json()["configured"]["schemaVersion"] == "hardware-configuration-v1"
    assert client.get("/api/v3/hardware/configuration/schema").json()["formats"] == ["oql", "yaml", "json"]

    content = client.get("/api/v3/hardware/configuration/source?format=json").json()["content"]
    assert client.post(
        "/api/v3/hardware/configuration/validate",
        json={"content": content, "format": "json"},
    ).status_code == 200
    denied = client.put(
        "/api/v3/hardware/configuration/source",
        headers={
            "X-Connect-Role": "password=hunter2",
            "X-Correlation-ID": "cor-hardware-config-role",
        },
        json={"content": content, "format": "json", "file_name": "oqlos.json"},
    )
    assert denied.status_code == 403
    assert denied.headers["content-type"].startswith("application/problem+json")
    denied_body = denied.json()
    assert denied_body["code"] == "C2004-AUTH-0002"
    assert denied_body["correlation_id"] == "cor-hardware-config-role"
    assert denied_body["component"] == "hardware-configuration"
    assert denied_body["stage"] == "role.authorize"
    assert (
        denied_body["metadata"]["diagnostics"]["issue_code"]
        == "api_hardware_configuration_write_forbidden"
    )
    assert "hunter2" not in denied.text
    assert client.put(
        "/api/v3/hardware/configuration/source",
        headers={"X-Connect-Role": "system"},
        json={"content": content, "format": "json", "file_name": "oqlos.json"},
    ).status_code == 200

    for path in (
        "/api/v3/hardware/mapping",
        "/api/v3/hardware/mapping/import",
        "/api/v3/hardware/mapping/export",
        "/api/v3/hardware/mapping/reset",
        "/api/v3/hardware/mapping/layer/persona",
        "/api/v3/hardware/oql-mapped-exec",
        "/api/v3/hardware/runtime-python/resolve-func",
    ):
        assert client.get(path).status_code == 404
