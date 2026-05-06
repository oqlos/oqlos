"""
oqlos/tests/test_core.py — Tests for CQL interpreter, parser, base classes, and firmware adapter.

Run: cd oqlos && python -m pytest tests/ -v
"""

from __future__ import annotations

import pytest
from pathlib import Path
from types import SimpleNamespace

import oqlos.config as oql_config
from oqlos.core.base import VariableStore, StepStatus
from oqlos.core.interpreter import CqlInterpreter
from oqlos.core.cql_parser import parse_cql, validate_cql
from oqlos.hardware.firmware_adapter import FirmwareAdapter, _parse_numeric, _PERIPHERAL_MAP, _SENSOR_MAP
from oqlos.shared.event_store import EventStore


# ═══════════════════════════════════════════════════════════════════════════════
# VariableStore
# ═══════════════════════════════════════════════════════════════════════════════

class TestVariableStore:
    def test_set_get(self):
        vs = VariableStore()
        vs.set("x", 42)
        assert vs.get("x") == 42
        assert vs.get("missing") is None
        assert vs.get("missing", "default") == "default"

    def test_interpolate_dollar(self):
        vs = VariableStore({"name": "Alice", "port": "8101"})
        assert vs.interpolate("Hello $name on port $port") == "Hello Alice on port 8101"

    def test_interpolate_braces(self):
        vs = VariableStore({"url": "http://localhost"})
        assert vs.interpolate("${url}/api") == "http://localhost/api"

    def test_interpolate_missing(self):
        vs = VariableStore()
        assert vs.interpolate("$missing stays") == "$missing stays"


# ═══════════════════════════════════════════════════════════════════════════════
# CQL Parser
# ═══════════════════════════════════════════════════════════════════════════════

CQL_SIMPLE = """\
# Simple CQL
SCENARIO: Test maski FPS 7000

GOAL: TEST WIZUALNY
  TASK: [Wyłącz] [Pump]
  TASK: [Potwierdź] [Test wizualny]
  SAVE [Test wizualny]
  SET [wait] = [7.0 s]
  MIN [AI01] = [-11.0 mbar]
  VAL [AI01] [mbar]
  IF [AI01] [<] [-11.0 mbar] ELSE ERROR "Wytworzenie podciśnienia"

GOAL: TEST SZCZELNOŚCI
  TASK: [Wyłącz] [Pump]
  MAX [AI01] = [-9.0 mbar]
  SAVE [AI01]
  SET [wait] = [60.0 s]
"""

CQL_CONNECTGO = """\
DEVICE_TYPE: "Aparat nadciśnieniowy"
DEVICE_MODEL: "DRAGER PSS 7000"
MANUFACTURER: "DRAGER A.G."

INTERVALS:
  - tt#000: "Po użyciu [M]" period: 0 months
  - tt#001: "Co 1 rok [M]" period: 12 months

@PSS7000.TestPrzezAdapter
  description: "Test kompletny przez adapter"
  intervals: [tt#000, tt#001]

  Przygotowanie:
    1. TEST WIZUALNY:
       → Operator.confirm "Kontrola wizualna"
       SAVE: result

  TestStatyczny:
    description: "TEST STATYCZNY"
    editable: true
    2. Pomiar ciśnienia:
       → Pump.off
       AI02 ∈ [6.0, 8.0] bar | ERROR "Ciśnienie poza zakresem"
       SAVE: AI02.value
"""

class TestCqlParser:
    def test_simple_metadata(self):
        doc = parse_cql(CQL_SIMPLE)
        assert doc.metadata.scenario_name == "Test maski FPS 7000"

    def test_parses_set_as_pump(self):
        doc = parse_cql("SCENARIO: Pump\n\nGOAL: Pompa\n  SET 'pompa' '5 bar'\n")
        assert len(doc.goals) == 1
        assert len(doc.goals[0].steps) == 1
        assert doc.goals[0].steps[0].actions[0].kind == "set"
        assert doc.goals[0].steps[0].actions[0].target == "pompa"
        assert doc.goals[0].steps[0].actions[0].args == "5 bar"

    def test_parses_set_command_for_valve_and_compressor(self):
        doc = parse_cql("SCENARIO: Set\n\nGOAL: Sterowanie\n  SET [zawór 2] = [1]\n  SET [sprężarka] = [120 l/min]\n")
        assert len(doc.goals) == 1
        actions = doc.goals[0].steps[0].actions
        assert [a.kind for a in actions] == ["set", "set"]
        assert actions[0].target == "zawór 2"
        assert actions[0].args == "1"
        assert actions[1].target == "sprężarka"
        assert actions[1].args == "120 l/min"

    def test_simple_goals(self):
        doc = parse_cql(CQL_SIMPLE)
        assert len(doc.goals) == 2
        assert doc.goals[0].name == "TEST WIZUALNY"
        assert doc.goals[1].name == "TEST SZCZELNOŚCI"

    def test_simple_actions(self):
        doc = parse_cql(CQL_SIMPLE)
        goal = doc.goals[0]
        assert len(goal.steps) == 1  # implicit step
        step = goal.steps[0]
        kinds = [a.kind for a in step.actions]
        assert "task" in kinds
        assert "save" in kinds
        assert "set" in kinds
        assert any(a.kind == "set" and a.target == "wait" for a in step.actions)
        assert "min" in kinds
        assert "val" in kinds
        assert "if_else" in kinds

    def test_connectgo_metadata(self):
        doc = parse_cql(CQL_CONNECTGO)
        assert doc.metadata.device_type == "Aparat nadciśnieniowy"
        assert doc.metadata.device_model == "DRAGER PSS 7000"
        assert doc.metadata.manufacturer == "DRAGER A.G."

    def test_connectgo_intervals(self):
        doc = parse_cql(CQL_CONNECTGO)
        assert len(doc.intervals) == 2
        assert doc.intervals[0].code == "tt#000"
        assert doc.intervals[0].period_months == 0
        assert doc.intervals[1].period_months == 12

    def test_connectgo_scenario(self):
        doc = parse_cql(CQL_CONNECTGO)
        assert len(doc.scenarios) == 1
        sc = doc.scenarios[0]
        assert sc.namespace == "PSS7000"
        assert sc.name == "TestPrzezAdapter"
        assert sc.description == "Test kompletny przez adapter"
        assert sc.intervals == ["tt#000", "tt#001"]

    def test_connectgo_goals(self):
        doc = parse_cql(CQL_CONNECTGO)
        sc = doc.scenarios[0]
        assert len(sc.goals) == 2
        assert sc.goals[0].name == "Przygotowanie"
        assert sc.goals[1].name == "TestStatyczny"
        assert sc.goals[1].editable is True

    def test_connectgo_steps(self):
        doc = parse_cql(CQL_CONNECTGO)
        sc = doc.scenarios[0]
        goal1 = sc.goals[0]
        assert len(goal1.steps) == 1
        assert goal1.steps[0].number == "1"
        assert "TEST WIZUALNY" in goal1.steps[0].name

    def test_connectgo_arrow_action(self):
        doc = parse_cql(CQL_CONNECTGO)
        sc = doc.scenarios[0]
        step = sc.goals[0].steps[0]
        arrow_actions = [a for a in step.actions if a.kind == "action"]
        assert len(arrow_actions) == 1
        assert arrow_actions[0].target == "Operator"
        assert arrow_actions[0].method == "confirm"

    def test_connectgo_condition(self):
        doc = parse_cql(CQL_CONNECTGO)
        sc = doc.scenarios[0]
        step = sc.goals[1].steps[0]
        conds = [a for a in step.actions if a.kind == "condition"]
        assert len(conds) == 1
        c = conds[0].condition
        assert c.sensor == "AI02"
        assert c.operator == "∈"
        assert c.value_min == 6.0
        assert c.value_max == 8.0
        assert c.on_fail == "ERROR"

    def test_connectgo_example_file(self):
        path = Path(__file__).resolve().parents[1] / "oqlos" / "scenarios" / "examples" / "pss7000.connectgo"
        doc = parse_cql(path.read_text(encoding="utf-8"), str(path))
        issues = validate_cql(doc)

        assert issues == []
        assert doc.warnings == []
        assert len(doc.scenarios) == 3
        assert [(s.namespace, s.name, len(s.goals)) for s in doc.scenarios] == [
            ("PSS7000", "TestPrzezAdapter", 8),
            ("PSS7000", "TestPrzezMaske", 8),
            ("PSS7000", "TestFenzyZenith", 7),
        ]
        assert len(doc.intervals) == 7
        assert sum(len(g.steps) for s in doc.scenarios for g in s.goals) == 23


class TestCqlValidator:
    def test_valid_document(self):
        doc = parse_cql(CQL_SIMPLE)
        issues = validate_cql(doc)
        assert len(issues) == 0

    def test_empty_document(self):
        doc = parse_cql("# empty")
        issues = validate_cql(doc)
        assert any("No SCENARIO" in i for i in issues)

    def test_invalid_interval_ref(self):
        doc = parse_cql(CQL_CONNECTGO)
        doc.scenarios[0].intervals = ["tt#999"]
        issues = validate_cql(doc)
        assert any("tt#999" in i for i in issues)


# ═══════════════════════════════════════════════════════════════════════════════
# CQL Interpreter
# ═══════════════════════════════════════════════════════════════════════════════

class TestCqlInterpreter:
    def test_dry_run_simple(self):
        interp = CqlInterpreter(mode="dry-run", quiet=True)
        result = interp.run(CQL_SIMPLE)
        assert len(result.steps) == 2
        assert result.steps[1].status == StepStatus.PASSED

    def test_dry_run_with_sensors(self):
        interp = CqlInterpreter(
            mode="dry-run", quiet=True,
            sensor_values={"AI01": -12.0, "AI02": 7.0},
        )
        result = interp.run(CQL_SIMPLE)
        assert len(result.steps) == 2

    def test_validate_mode(self):
        interp = CqlInterpreter(mode="validate", quiet=True)
        result = interp.run(CQL_SIMPLE)
        assert result.ok is True

    def test_set_actions_store_variables(self):
        interp = CqlInterpreter(mode="dry-run", quiet=True)
        result = interp.run("SCENARIO: Set\n\nGOAL: Sterowanie\n  SET [zawór 2] = [1]\n  SET [sprężarka] = [120 l/min]\n")
        assert result.ok is True
        assert interp.vars.get("zawór 2") == "1"
        assert interp.vars.get("sprężarka") == "120 l/min"

    def test_variables_saved(self):
        interp = CqlInterpreter(mode="dry-run", quiet=True, sensor_values={"AI01": 5.0})
        result = interp.run(CQL_SIMPLE)
        assert "AI01" in result.variables


class TestCqlExecuteMode:
    def test_execute_mode_initializes_firmware(self):
        interp = CqlInterpreter(mode="execute", quiet=True, firmware_url="http://localhost:9999")
        assert interp._firmware is None
        assert interp._firmware_url == "http://localhost:9999"

    def test_pump_flow_uses_env_scale(self, monkeypatch):
        calls: list[tuple[str, float]] = []

        class FakeFirmware:
            def set_peripheral(self, target: str, value):
                calls.append((target, value))
                return {"ok": True}

        monkeypatch.setattr(
            oql_config,
            "get_settings",
            lambda: SimpleNamespace(pump_flow_full_scale_lpm=20.0),
        )

        interp = CqlInterpreter(mode="execute", quiet=True)
        monkeypatch.setattr(interp, "_get_firmware", lambda: FakeFirmware())

        result = interp.run("SCENARIO: Pump\nGOAL: Demo\n  SET 'pompa 1' '10 l/min'\n")

        assert result.ok is True
        assert calls == [("pompa 1", 50.0)]

    def test_pump_compact_liter_value_uses_flow_scale(self, monkeypatch):
        calls: list[tuple[str, float]] = []

        class FakeFirmware:
            def set_peripheral(self, target: str, value):
                calls.append((target, value))
                return {"ok": True}

        monkeypatch.setattr(
            oql_config,
            "get_settings",
            lambda: SimpleNamespace(pump_flow_full_scale_lpm=10.0),
        )

        interp = CqlInterpreter(mode="execute", quiet=True)
        monkeypatch.setattr(interp, "_get_firmware", lambda: FakeFirmware())

        result = interp.run("SCENARIO: Pump\nGOAL: Demo\n  SET 'PUMP' '5l'\n")

        assert result.ok is True
        assert calls == [("PUMP", 50.0)]

    def test_pump_flow_scale_can_be_overridden_in_config_block(self, monkeypatch):
        calls: list[tuple[str, float]] = []

        class FakeFirmware:
            def set_peripheral(self, target: str, value):
                calls.append((target, value))
                return {"ok": True}

        monkeypatch.setattr(
            oql_config,
            "get_settings",
            lambda: SimpleNamespace(pump_flow_full_scale_lpm=10.0),
        )

        interp = CqlInterpreter(mode="execute", quiet=True)
        monkeypatch.setattr(interp, "_get_firmware", lambda: FakeFirmware())

        src = """SCENARIO: Pump config

CONFIG: Kalibracja pompy
  SET 'PUMP_FLOW_FULL_SCALE_LPM' '20'

GOAL: Test przepływu
  SET 'pompa 1' '10 l/min'
"""

        result = interp.run(src)

        assert result.ok is True
        assert interp.vars.get("PUMP_FLOW_FULL_SCALE_LPM") == "20"
        assert calls == [("pompa 1", 50.0)]

    def test_dry_run_does_not_use_firmware(self):
        src = """SCENARIO: Test
GOAL: Test goal
  TASK: [Wyłącz] [Pump]
"""
        interp = CqlInterpreter(mode="dry-run", quiet=True)
        result = interp.run(src)
        assert result.ok is True
        assert interp._firmware is None

    def test_auto_mock_seeds_default_sensors(self):
        interp = CqlInterpreter(mode="dry-run", quiet=True)
        assert "AI01" in interp.sensor_values
        assert "AI02" in interp.sensor_values

    def test_auto_mock_range_condition_passes(self):
        src = """SCENARIO: Auto-mock test
GOAL: Pressure check
  1. Check:
     AI01 ∈ [-20.0, -5.0] mbar   | ERROR "Pressure out of range"
"""
        interp = CqlInterpreter(mode="dry-run", quiet=True)
        result = interp.run(src)
        assert result.ok is True
        assert result.failed == 0

    def test_auto_mock_disabled(self):
        src = """SCENARIO: No auto-mock
GOAL: Check
  1. Check:
     AI01 ∈ [100.0, 200.0] mbar   | ERROR "Out of range"
"""
        interp = CqlInterpreter(mode="dry-run", quiet=True, auto_mock=False)
        result = interp.run(src)
        assert result.failed >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# FirmwareAdapter (unit tests — no HTTP)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFirmwareAdapterUnit:
    def _firmware_with_post_response(self, payload: dict):
        class Response:
            def __init__(self, data: dict):
                self._data = data

            def json(self):
                return self._data

            def raise_for_status(self):
                return None

        class Client:
            def __init__(self, data: dict):
                self._data = data
                self.post_calls = []
                self.put_calls = []

            def post(self, url, params=None, json=None):
                self.post_calls.append((url, params, json))
                return Response(self._data)

            def put(self, url, json=None):
                self.put_calls.append((url, json))
                return Response({"ok": True})

        fw = FirmwareAdapter.__new__(FirmwareAdapter)
        fw.base_url = "http://localhost:8202"
        fw.timeout = 5.0
        fw._client = Client(payload)
        fw.lung_motor_url = "http://localhost:8205"
        return fw, fw._client

    def test_peripheral_map_completeness(self):
        assert _PERIPHERAL_MAP["pump"] == "pump-main"
        assert _PERIPHERAL_MAP["valve"] == "valve-1"
        assert _PERIPHERAL_MAP["valve-outlet"] == "valve-2"

    def test_sensor_map(self):
        assert _SENSOR_MAP["AI01"] == "nc-sensor"
        assert _SENSOR_MAP["AI02"] == "sc-sensor"
        assert _SENSOR_MAP["AI03"] == "wc-sensor"

    def test_parse_numeric(self):
        assert _parse_numeric("5l") == 5.0
        assert _parse_numeric("7.0 mbar") == 7.0
        assert _parse_numeric("-11.0 mbar") == -11.0
        assert _parse_numeric("100%") == 100.0
        assert _parse_numeric("") == 0.0

    def test_resolve_peripheral(self):
        fw = FirmwareAdapter.__new__(FirmwareAdapter)
        fw.base_url = "http://localhost:8202"
        fw.timeout = 5.0
        fw._client = None
        assert fw._resolve_peripheral("Pump") == "pump-main"
        assert fw._resolve_peripheral("pompa 2") == "pump-main"
        assert fw._resolve_peripheral("Valve") == "valve-1"
        assert fw._resolve_peripheral("valve-outlet") == "valve-2"
        assert fw._resolve_peripheral("unknown-device") == "unknown-device"

    def test_dispatch_confirm_no_http(self):
        fw = FirmwareAdapter.__new__(FirmwareAdapter)
        fw.base_url = "http://localhost:8202"
        fw.timeout = 5.0
        fw._client = None
        result = fw.dispatch_action("Operator", "confirm", "Kontrola wizualna")
        assert result["ok"] is True
        assert "confirmed" in result["detail"]

    def test_set_peripheral_pump_rejects_nested_failed_response(self):
        fw, client = self._firmware_with_post_response(
            {
                "power_pct": 1.0,
                "ok": {
                    "success": False,
                    "error": "Value 1.0 not in allowed raster",
                },
            }
        )

        with pytest.raises(RuntimeError, match="allowed raster"):
            fw.set_peripheral("pompa-1", 1)

        assert client.put_calls == []

    def test_dispatch_pump_reports_hardware_rejection(self):
        fw, _client = self._firmware_with_post_response(
            {
                "power_pct": 1.0,
                "ok": {
                    "success": False,
                    "error": "Value 1.0 not in allowed raster",
                },
            }
        )

        result = fw.dispatch_action("Pump", "set", "1")

        assert result["ok"] is False
        assert "allowed raster" in result["detail"]

    def test_dispatch_lung_falls_back_to_direct_service_on_404(self, monkeypatch):
        import httpx

        from oqlos.hardware import firmware_adapter as firmware_adapter_module

        class BridgeClient:
            def post(self, url, params=None, json=None):
                request = httpx.Request("POST", f"http://localhost:8202{url}")
                return httpx.Response(404, request=request)

            def close(self):
                return None

        class DirectClient:
            def __init__(self, base_url: str, timeout: float):
                self.base_url = base_url.rstrip("/")

            def post(self, url, params=None, json=None):
                request = httpx.Request("POST", f"{self.base_url}{url}")
                return httpx.Response(200, json={"ok": True, "service": "tic249"}, request=request)

            def close(self):
                return None

        created_urls: list[str] = []

        def fake_client(*, base_url, timeout):
            created_urls.append(base_url.rstrip("/"))
            if base_url.rstrip("/").endswith("8205"):
                return DirectClient(base_url, timeout)
            raise AssertionError(f"Unexpected client base URL: {base_url}")

        monkeypatch.setattr(firmware_adapter_module.httpx, "Client", fake_client)

        fw = FirmwareAdapter.__new__(FirmwareAdapter)
        fw.base_url = "http://localhost:8202"
        fw.timeout = 5.0
        fw._client = BridgeClient()
        fw.lung_motor_url = "http://localhost:8205"

        result = fw.set_peripheral("lung", 2)

        assert result["ok"] is True
        assert result["service"] == "tic249"
        assert created_urls == ["http://localhost:8205"]


# ═══════════════════════════════════════════════════════════════════════════════
# EventStore
# ═══════════════════════════════════════════════════════════════════════════════

class TestEventStore:
    def test_append_and_get(self):
        store = EventStore()
        store.append({"type": "test", "correlationId": "abc"})
        assert store.count == 1
        assert store.get_all()[0]["type"] == "test"

    def test_get_recent(self):
        store = EventStore()
        for i in range(10):
            store.append({"idx": i})
        recent = store.get_recent(3)
        assert len(recent) == 3
        assert recent[0]["idx"] == 7

    def test_get_by_correlation(self):
        store = EventStore()
        store.append({"correlationId": "a"})
        store.append({"correlationId": "b"})
        store.append({"correlationId": "a"})
        assert len(store.get_by_correlation("a")) == 2

    def test_clear(self):
        store = EventStore()
        store.append({"type": "x"})
        store.clear()
        assert store.count == 0

    def test_json_roundtrip(self):
        store = EventStore()
        store.append({"type": "test"})
        j = store.to_json()
        store2 = EventStore()
        store2.from_json(j)
        assert store2.count == 1

    def test_persistence(self, tmp_path):
        path = str(tmp_path / "events.json")
        s1 = EventStore(persist_path=path)
        s1.append({"type": "persisted"})
        s2 = EventStore(persist_path=path)
        assert s2.count == 1
        assert s2.get_all()[0]["type"] == "persisted"
