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
        self.out = SimpleNamespace(output_yaml=lambda: None)

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
            "modbus-adc": "ok",
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
                {"id": "modbus-adc", "status": "ok"},
                {"id": "motor-tic249", "status": "ok"},
                {"id": "motor-dri0050", "status": "ok"},
                {"id": "modbus-io", "status": "ok"},
            ],
        }

    def fake_ensure_firmware_running(url: str, *, quiet: bool, yaml_output: bool) -> bool:
        captured.setdefault("ensure_firmware_urls", []).append(url)
        return True

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
    monkeypatch.setattr(cql_cli, "_ensure_firmware_running", fake_ensure_firmware_running)
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
        "VERSION: 4\n"
        "SCENARIO: Single command\n"
        "GOAL:\n"
        "  SET NAME 'Execute command'\n"
        "  SET 'pompa 1' '0'\n"
    )


def test_cmd_execute_aborts_when_hardware_is_unavailable(monkeypatch, capsys):
    def fake_health(url: str) -> dict[str, object]:
        return {"error": f"Connection refused at {url}"}

    def fake_identify(url: str) -> dict[str, object]:
        pytest.fail(f"identify should not be called when health fails: {url}")

    def fake_ensure_firmware_running(url: str, *, quiet: bool, yaml_output: bool) -> bool:
        return True

    class FakeInterpreter(_FakeInterpreter):
        def __init__(self, **kwargs):
            raise AssertionError("Interpreter should not be created when preflight fails")

    monkeypatch.setattr(cql_cli, "check_firmware_health", fake_health)
    monkeypatch.setattr(cql_cli, "check_firmware_identify", fake_identify)
    monkeypatch.setattr(cql_cli, "_ensure_firmware_running", fake_ensure_firmware_running)
    monkeypatch.setattr(cql_cli, "CqlInterpreter", FakeInterpreter)
    monkeypatch.setattr(sys, "argv", ["oqlctl", "cmd", "SET 'pompa 1' '0'"])

    with pytest.raises(SystemExit) as excinfo:
        cql_cli.main()

    assert excinfo.value.code == 1
    assert "Hardware preflight failed" in capsys.readouterr().out


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


def test_run_subcommand_executes_scenario_file(monkeypatch, tmp_path):
    captured: dict[str, object] = {}
    scenario_file = tmp_path / "scenario.oql"
    scenario_file.write_text("SCENARIO: Test\nGOAL: Demo\n  SET 'pompa 1' '0'\n", encoding="utf-8")

    class FakeInterpreter(_FakeInterpreter):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            captured["init"] = kwargs

        def run_file(self, path: str):
            captured["path"] = path
            return super().run("", path)

    monkeypatch.setattr(cql_cli, "CqlInterpreter", FakeInterpreter)
    monkeypatch.setattr(sys, "argv", ["oqlctl", "run", str(scenario_file), "--mode", "dry-run"])

    cql_cli.main()

    assert captured["path"] == str(scenario_file)
    assert captured["init"]["mode"] == "dry-run"


def test_format_subcommand_prints_canonical_set_syntax(monkeypatch, tmp_path, capsys):
    scenario_file = tmp_path / "legacy.oql"
    scenario_file.write_text(
        "VERSION: 4\n"
        "GOAL:\n"
        "  SET [zawor 3] = [ON]\n"
        "  SET tryb = TEST\n"
        "  SET [motor 2] limit 1000 steps/s\n"
        "  SET NAME [Keep goal name syntax]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", ["oqlctl", "format", str(scenario_file)])

    cql_cli.main()

    assert capsys.readouterr().out == (
        "VERSION: 4\n"
        "GOAL:\n"
        "  SET 'zawor 3' 'ON'\n"
        "  SET 'tryb' 'TEST'\n"
        "  SET 'motor 2' 'limit 1000 steps/s'\n"
        "  SET NAME 'Keep goal name syntax'\n"
    )


def test_format_subcommand_write_updates_file(monkeypatch, tmp_path):
    scenario_file = tmp_path / "legacy.oql"
    scenario_file.write_text("GOAL:\n  SET valve-nc 1\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["oqlctl", "format", str(scenario_file), "--write"])

    cql_cli.main()

    assert scenario_file.read_text(encoding="utf-8") == "GOAL:\n  SET 'valve-nc' '1'\n"


def test_run_subcommand_fetches_scenario_url(monkeypatch):
    import importlib

    main_module = importlib.import_module("oqlos.tools.cql_cli.main")
    captured: dict[str, object] = {}

    class FakeInterpreter(_FakeInterpreter):
        def run(self, source: str, filename: str):
            captured["source"] = source
            captured["filename"] = filename
            return super().run(source, filename)

    monkeypatch.setattr(main_module, "CqlInterpreter", FakeInterpreter)
    monkeypatch.setattr(
        main_module,
        "_fetch_scenario_source",
        lambda url: "SCENARIO: From URL\nGOAL: Demo\n  SET 'pompa 1' '0'\n",
    )

    main_module._dispatch_to_mode([
        "run",
        "http://localhost:8096/scenarios?scenario=maskleaktest-nadcisnieniestatyczne",
        "--mode",
        "dry-run",
    ])

    assert captured["filename"] == "http://localhost:8096/scenarios?scenario=maskleaktest-nadcisnieniestatyczne"
    assert "SCENARIO: From URL" in captured["source"]


def test_fetch_scenario_source_rejects_editor_html(monkeypatch):
    import importlib

    main_module = importlib.import_module("oqlos.tools.cql_cli.main")

    class FakeResponse:
        headers = {"content-type": "text/html"}
        text = "<!DOCTYPE html><html><body><div id='root'></div></body></html>"

        def raise_for_status(self):
            return None

    monkeypatch.setattr("httpx.get", lambda url, timeout: FakeResponse())

    with pytest.raises(main_module.ScenarioFetchError, match="returned HTML"):
        main_module._fetch_scenario_source("http://localhost:8096/scenarios?scenario=demo")


def test_run_subcommand_reports_url_fetch_error(monkeypatch, capsys):
    import importlib

    main_module = importlib.import_module("oqlos.tools.cql_cli.main")

    class FakeInterpreter(_FakeInterpreter):
        pass

    def fake_fetch(url: str):
        raise main_module.ScenarioFetchError("URL returned HTML, not OQL/CQL source")

    monkeypatch.setattr(main_module, "CqlInterpreter", FakeInterpreter)
    monkeypatch.setattr(main_module, "_fetch_scenario_source", fake_fetch)

    with pytest.raises(SystemExit) as excinfo:
        main_module._dispatch_to_mode([
            "run",
            "http://localhost:8096/scenarios?scenario=demo",
            "--mode",
            "dry-run",
            "--json",
        ])

    payload = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 1
    assert payload["status"] == "error"
    assert "not OQL/CQL source" in payload["message"]


def test_cmd_execute_mock_mode_error_suggests_dry_run_and_doctor(monkeypatch, capsys):
    def fake_health(url: str) -> dict[str, object]:
        return {"mode": "mock", "note": "mock mode - no hardware calls"}

    def fake_identify(url: str) -> dict[str, object]:
        pytest.fail(f"identify should not be called when mode is mock: {url}")

    def fake_ensure_firmware_running(url: str, *, quiet: bool, yaml_output: bool) -> bool:
        return True

    class FakeInterpreter(_FakeInterpreter):
        def __init__(self, **kwargs):
            raise AssertionError("Interpreter should not be created when preflight fails")

    monkeypatch.setattr(cql_cli, "check_firmware_health", fake_health)
    monkeypatch.setattr(cql_cli, "check_firmware_identify", fake_identify)
    monkeypatch.setattr(cql_cli, "_ensure_firmware_running", fake_ensure_firmware_running)
    monkeypatch.setattr(cql_cli, "CqlInterpreter", FakeInterpreter)
    monkeypatch.setattr(sys, "argv", ["oqlctl", "cmd", "SET pompa-1 0"])

    with pytest.raises(SystemExit) as excinfo:
        cql_cli.main()

    output = capsys.readouterr().out
    assert excinfo.value.code == 1
    assert "--mode dry-run" in output
    assert "oqlctl doctor" in output


def test_cmd_execute_blocks_when_required_adapter_health_is_bad(monkeypatch, capsys):
    def fake_health(url: str) -> dict[str, object]:
        return {"mode": "real", "motor": "error: connection refused"}

    def fake_identify(url: str) -> dict[str, object]:
        return {
            "mode": "real",
            "detected": 1,
            "total": 4,
            "adapters": [{"id": "motor-dri0050", "status": "ok"}],
        }

    def fake_ensure_firmware_running(url: str, *, quiet: bool, yaml_output: bool) -> bool:
        return True

    class FakeInterpreter(_FakeInterpreter):
        def __init__(self, **kwargs):
            raise AssertionError("Interpreter should not run when motor health is bad")

    monkeypatch.setattr(cql_cli, "check_firmware_health", fake_health)
    monkeypatch.setattr(cql_cli, "check_firmware_identify", fake_identify)
    monkeypatch.setattr(cql_cli, "_ensure_firmware_running", fake_ensure_firmware_running)
    monkeypatch.setattr(cql_cli, "CqlInterpreter", FakeInterpreter)
    monkeypatch.setattr(sys, "argv", ["oqlctl", "cmd", "SET pompa-1 0"])

    with pytest.raises(SystemExit) as excinfo:
        cql_cli.main()

    output = capsys.readouterr().out
    assert excinfo.value.code == 1
    assert "motor-dri0050" in output
    assert "connection refused" in output


def test_oqlctl_doctor_subcommand_dispatches_to_hardware_flags(monkeypatch):
    import importlib

    main_module = importlib.import_module("oqlos.tools.cql_cli.main")

    captured = {}

    def fake_run_hardware_flags(args):
        captured["args"] = args
        return True

    monkeypatch.setattr(main_module, "_run_hardware_flags", fake_run_hardware_flags)

    main_module.run_hardware_mode("doctor", ["--firmware-url", "http://example.test", "--config", "custom.yaml", "--fix", "--json"])

    assert captured["args"].doctor is True
    assert captured["args"].fix is True
    assert captured["args"].json is True
    assert captured["args"].firmware_url == "http://example.test"
    assert captured["args"].config == "custom.yaml"


def test_oqlctl_status_flag_dispatches_without_file(monkeypatch):
    import importlib

    main_module = importlib.import_module("oqlos.tools.cql_cli.main")

    captured = {}

    def fake_run_hardware_flags(args):
        captured["status"] = args.status
        return True

    monkeypatch.setattr(main_module, "_run_hardware_flags", fake_run_hardware_flags)
    args = main_module.create_file_parser().parse_args(["--status"])

    main_module.run_file_mode(args)

    assert captured["status"] is True


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
