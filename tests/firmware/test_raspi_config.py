from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from oqlos.api.main import app
from oqlos.hardware.raspi_config import (
    RaspiConfigError,
    apply_raspi_config,
    parse_raspi_configuration,
    plan_raspi_config,
    serialize_raspi_configuration,
)


FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "raspi-config"


def test_oql_examples_round_trip() -> None:
    for name in ("boardnet.oql", "displaynet.oql"):
        source = (FIXTURES / name).read_text(encoding="utf-8")
        config = parse_raspi_configuration(source, "oql")
        assert config.schema_version == "raspi-config-v1"
        assert config.interfaces.i2c is True
        assert config.interfaces.ssh is True
        if name == "boardnet.oql":
            assert config.wifi_country is None
        else:
            assert config.wifi_country == "PL"
        dumped = serialize_raspi_configuration(config, "oql")
        assert parse_raspi_configuration(dumped, "oql") == config


def test_secret_fields_are_rejected() -> None:
    with pytest.raises(RaspiConfigError, match="secret"):
        parse_raspi_configuration(
            '{"schemaVersion":"raspi-config-v1","wifiPsk":"hunter2"}',
            "json",
        )


def test_plan_uses_fixed_nonint_argv() -> None:
    desired = parse_raspi_configuration((FIXTURES / "boardnet.oql").read_text(), "oql")
    steps = plan_raspi_config(
        desired,
        {
            "supported": True,
            "interfaces": {"i2c": False, "spi": False, "ssh": True, "vnc": False, "serial_hw": True, "serial_cons": True},
            "wifiCountry": "DE",
        },
    )
    by_key = {step["key"]: step for step in steps}
    assert by_key["interfaces.i2c"]["argv"] == ["do_i2c", "0"]
    assert by_key["interfaces.i2c"]["changed"] is True
    assert by_key["interfaces.ssh"]["changed"] is False
    assert "wifiCountry" not in by_key


def test_apply_dry_run_does_not_call_raspi_config(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def run(args: list[str], **_kwargs: Any) -> Any:
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="0\n")

    monkeypatch.setattr(
        "oqlos.hardware.raspi_config.probe_raspi_config",
        lambda **_kwargs: {
            "supported": True,
            "interfaces": {"i2c": True, "ssh": True, "spi": False},
            "wifiCountry": "PL",
        },
    )
    desired = parse_raspi_configuration((FIXTURES / "displaynet.oql").read_text(), "oql")
    result = apply_raspi_config(desired, dry_run=True, runner=run)
    assert result["dry_run"] is True
    assert calls == []


def test_apply_requires_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OQLOS_ALLOW_RASPI_CONFIG", raising=False)
    monkeypatch.setattr("oqlos.hardware.raspi_config.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        "oqlos.hardware.raspi_config.probe_raspi_config",
        lambda **_kwargs: {"supported": True, "interfaces": {"i2c": False}, "wifiCountry": None},
    )
    desired = parse_raspi_configuration(
        '{"schemaVersion":"raspi-config-v1","interfaces":{"i2c":true}}',
        "json",
    )
    with pytest.raises(RaspiConfigError, match="OQLOS_ALLOW_RASPI_CONFIG"):
        apply_raspi_config(desired, dry_run=False, runner=lambda *_a, **_k: SimpleNamespace(returncode=0, stdout=""))


def test_apply_runs_only_changed_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setenv("OQLOS_ALLOW_RASPI_CONFIG", "1")
    monkeypatch.setattr(
        "oqlos.hardware.raspi_config.probe_raspi_config",
        lambda **_kwargs: {
            "supported": True,
            "interfaces": {"i2c": False, "ssh": True},
            "wifiCountry": "PL",
        },
    )

    def run(args: list[str], **_kwargs: Any) -> Any:
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="")

    desired = parse_raspi_configuration(
        '{"schemaVersion":"raspi-config-v1","interfaces":{"i2c":true,"ssh":true},"wifiCountry":"PL"}',
        "json",
    )
    result = apply_raspi_config(desired, dry_run=False, runner=run)
    assert calls == [["do_i2c", "0"]]
    assert result["ok"] is True


def test_raspi_config_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "oqlos.api.raspi_config_routes.probe_raspi_config",
        lambda: {"supported": False, "interfaces": {}, "wifiCountry": None, "error": "missing"},
    )
    client = TestClient(app)
    status = client.get("/api/v3/hardware/raspi-config")
    assert status.status_code == 200
    assert status.json()["contract"] == "raspi-config-v1"

    content = (FIXTURES / "displaynet.oql").read_text(encoding="utf-8")
    validated = client.post(
        "/api/v3/hardware/raspi-config/validate",
        json={"content": content, "format": "oql"},
    )
    assert validated.status_code == 200
    assert validated.json()["configuration"]["wifiCountry"] == "PL"

    denied = client.post(
        "/api/v3/hardware/raspi-config/apply",
        headers={"X-Connect-Role": "viewer"},
        json={"content": content, "format": "oql", "dry_run": False, "confirm": True},
    )
    assert denied.status_code == 403

    planned = client.post(
        "/api/v3/hardware/raspi-config/apply",
        json={"content": content, "format": "oql", "dry_run": True},
    )
    assert planned.status_code == 200
    assert planned.json()["dry_run"] is True
