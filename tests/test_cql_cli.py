"""Tests for the OQL/CQL CLI."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

from oqlos.tools import cql_cli


class _FakeInterpreter:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def run(self, source: str, filename: str):
        return SimpleNamespace(
            source=filename,
            ok=True,
            passed=1,
            failed=0,
            steps=[],
            duration_ms=1.0,
            errors=[],
            warnings=[],
            variables={},
            _source=source,
        )


def test_cmd_executes_single_command(monkeypatch):
    captured: dict[str, object] = {}

    def fake_health(url: str) -> dict[str, object]:
        captured.setdefault("health_urls", []).append(url)
        return {
            "mode": "real",
            "piadc": "ok",
            "motor": "ok",
            "lung": "ok",
            "modbus": "ok",
        }

    def fake_identify(url: str) -> dict[str, object]:
        captured.setdefault("identify_urls", []).append(url)
        return {
            "mode": "real",
            "detected": 4,
            "total": 4,
            "adapters": [
                {"id": "piadc", "status": "ok"},
                {"id": "motor-tic249", "status": "ok"},
                {"id": "motor-dri0050", "status": "ok"},
                {"id": "modbus-io", "status": "ok"},
            ],
        }

    class FakeInterpreter(_FakeInterpreter):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            captured["init"] = kwargs

        def run(self, source: str, filename: str):
            captured["source"] = source
            captured["filename"] = filename
            return super().run(source, filename)

    monkeypatch.setattr(cql_cli, "check_firmware_health", fake_health)
    monkeypatch.setattr(cql_cli, "check_firmware_identify", fake_identify)
    monkeypatch.setattr(cql_cli, "CqlInterpreter", FakeInterpreter)
    monkeypatch.setattr(sys, "argv", ["oqlctl", "cmd", "SET 'pompa 1' '0'"])

    cql_cli.main()

    assert captured["filename"] == "<cmd>"
    assert captured["init"]["mode"] == "execute"
    assert captured["init"]["quiet"] is False
    assert captured["init"]["firmware_url"] == cql_cli.DEFAULT_FIRMWARE_URL
    assert captured["health_urls"] == [cql_cli.DEFAULT_FIRMWARE_URL]
    assert captured["identify_urls"] == [cql_cli.DEFAULT_FIRMWARE_URL]
    assert captured["source"] == (
        'SCENARIO: "Single command"\n'
        'GOAL: Execute command\n'
        '  1. Run command:\n'
        "    SET 'pompa 1' '0'\n"
    )


def test_cmd_execute_aborts_when_hardware_is_unavailable(monkeypatch, capsys):
    def fake_health(url: str) -> dict[str, object]:
        return {"error": f"Connection refused at {url}"}

    def fake_identify(url: str) -> dict[str, object]:
        pytest.fail(f"identify should not be called when health fails: {url}")

    class FakeInterpreter(_FakeInterpreter):
        def __init__(self, **kwargs):
            raise AssertionError("Interpreter should not be created when preflight fails")

    monkeypatch.setattr(cql_cli, "check_firmware_health", fake_health)
    monkeypatch.setattr(cql_cli, "check_firmware_identify", fake_identify)
    monkeypatch.setattr(cql_cli, "CqlInterpreter", FakeInterpreter)
    monkeypatch.setattr(sys, "argv", ["oqlctl", "cmd", "SET 'pompa 1' '0'"])

    with pytest.raises(SystemExit) as excinfo:
        cql_cli.main()

    assert excinfo.value.code == 1
    assert "Hardware preflight failed" in capsys.readouterr().err


def test_file_mode_still_executes_scenario(monkeypatch, tmp_path):
    captured: dict[str, object] = {}
    scenario_file = tmp_path / "scenario.oql"
    scenario_file.write_text(
        "SCENARIO: Test\nGOAL: Demo\n  1. Run:\n    SET 'pompa 1' '0'\n",
        encoding="utf-8",
    )

    class FakeInterpreter(_FakeInterpreter):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            captured["init"] = kwargs

        def run_file(self, path: str):
            captured["path"] = path
            return super().run("", path)

    monkeypatch.setattr(cql_cli, "CqlInterpreter", FakeInterpreter)
    monkeypatch.setattr(sys, "argv", ["oqlctl", str(scenario_file), "--mode", "execute"])

    cql_cli.main()

    assert captured["path"] == str(scenario_file)
    assert captured["init"]["mode"] == "execute"


def test_result_payload_is_json_safe():
    result = SimpleNamespace(
        source="<cmd>",
        ok=True,
        passed=1,
        failed=0,
        steps=[SimpleNamespace(name="1. Run command", status=SimpleNamespace(value="passed"), message="")],
        duration_ms=12.345,
        errors=[],
        warnings=[],
        variables={"pump": "0"},
    )

    payload = cql_cli._result_payload(result)

    assert json.loads(json.dumps(payload, ensure_ascii=False))["variables"]["pump"] == "0"
