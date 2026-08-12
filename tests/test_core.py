"""
oqlos/tests/test_core.py — Tests for CQL interpreter, parser, base classes, and firmware adapter.

Run: cd oqlos && python -m pytest tests/ -v
"""

from __future__ import annotations

import os

import pytest
from pathlib import Path
from types import SimpleNamespace

import oqlos.config as oql_config
import oqlos.core._interpreter_actions as interpreter_actions
from oqlos.core.base import VariableStore, StepStatus
from oqlos.core.interpreter import CqlInterpreter, OqlInterpreter
from oqlos.core.motor2_runtime import build_motor2_reciprocating_plan, normalize_motor2_runtime_config
from oqlos.core.cql_parser import parse_cql, validate_cql
from oqlos.hardware.firmware_adapter import FirmwareAdapter, _parse_numeric, _PERIPHERAL_MAP, _SENSOR_MAP
from oqlos.shared.event_store import EventStore


def _scenario_example_path(name: str) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    scenarios_root = Path(
        os.environ.get("OQLOS_SCENARIOS_DIR", repo_root.parent / "oql-scenario")
    )
    return scenarios_root / "examples" / name


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
  SET WAIT '7.0 s'
  MIN [AI01] = [-11.0 mbar]
  VAL [AI01] [mbar]
  IF [AI01] [<] [-11.0 mbar] ELSE ERROR "Wytworzenie podciśnienia"

GOAL: TEST SZCZELNOŚCI
  TASK: [Wyłącz] [Pump]
  MAX [AI01] = [-9.0 mbar]
  SAVE [AI01]
  SET WAIT '60.0 s'
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
        assert "wait" in kinds
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
        path = _scenario_example_path("pss7000.connectgo")
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
    def test_public_oql_interpreter_alias(self):
        assert OqlInterpreter is CqlInterpreter

    def test_public_execution_header_uses_oql_name(self, capsys):
        interp = CqlInterpreter(mode="dry-run", quiet=False)

        interp.run(CQL_SIMPLE)

        output = capsys.readouterr().out
        assert "OQL:" in output
        assert "CQL:" not in output

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

    def test_connectgo_oql_example_file_dry_runs(self):
        path = _scenario_example_path("mask-leak-test.oql")
        interp = CqlInterpreter(mode="dry-run", quiet=True)
        result = interp.run_file(str(path))

        assert result.ok is True
        assert result.errors == []
        assert result.warnings == []
        assert result.passed > 0


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

    def test_version4_textual_hardware_set_values_execute(self, monkeypatch):
        calls: list[tuple[str, object]] = []

        class FakeFirmware:
            def set_peripheral(self, target: str, value):
                calls.append((target, value))
                return {"ok": True}

        monkeypatch.setattr(
            oql_config,
            "get_settings",
            lambda: SimpleNamespace(pump_flow_full_scale_lpm=10.0),
        )

        interp = CqlInterpreter(mode="execute", quiet=True, skip_waits=True)
        monkeypatch.setattr(interp, "_get_firmware", lambda: FakeFirmware())

        src = """VERSION: 4
GOAL:
  SET NAME 'Hardware smoke'
  SET 'zawor 3' 'ON'
  SET 'PUMP' '5l'
  SET WAIT '1 s'
  SET 'zawor 1' 'OFF'
  SET 'PUMP' 'OFF'
"""

        result = interp.run(src)

        assert result.ok is True
        assert calls == [
            ("zawor 3", True),
            ("PUMP", 50.0),
            ("zawor 1", False),
            ("PUMP", 0.0),
        ]

    def test_motor2_reciprocating_oql_execute_uses_reciprocate_not_relative_move(self, monkeypatch):
        reciprocate_calls: list[dict[str, object]] = []
        stop_calls: list[bool] = []

        def fake_reciprocate(direction, steps, speed_raw, acceleration_raw, cycles, pause, limit_mode):
            reciprocate_calls.append(
                {
                    "direction": direction,
                    "steps": steps,
                    "speed_raw": speed_raw,
                    "acceleration_raw": acceleration_raw,
                    "cycles": cycles,
                    "pause": pause,
                    "limit_mode": limit_mode,
                }
            )

        monkeypatch.setattr(interpreter_actions, "_post_motor2_reciprocate", fake_reciprocate)
        monkeypatch.setattr(interpreter_actions, "_post_motor2_stop", lambda: stop_calls.append(True))
        monkeypatch.setattr(
            interpreter_actions,
            "_post_motor2_move_relative",
            lambda *args, **kwargs: pytest.fail("limit steps/s must not be executed as a relative move"),
        )

        src = """VERSION: 4
GOAL:
  SET NAME 'Test goal'
  SET 'motor 2' 'reciprocating motion'
  SET 'motor 2' 'limit 1000 steps/s'
  SET 'motor 2' 'acceleration 100%/s'
  SET 'motor 2' 'reverse on limit'
  SET 'motor 2' 'start left direction'
  SET 'motor 2' 'stop'
"""

        interp = CqlInterpreter(mode="execute", quiet=True)
        result = interp.run(src)

        assert result.ok is True
        assert reciprocate_calls == [
            {
                "direction": "left",
                "steps": 1000,
                "speed_raw": 10_000_000,
                "acceleration_raw": 100_000,
                "cycles": 1_000_000,
                "pause": 0.0,
                "limit_mode": "reverse_on_limit",
            }
        ]
        assert stop_calls == [True]

    def test_motor2_explicit_relative_move_keeps_steps_and_speed_separate(self, monkeypatch):
        calls: list[dict[str, object]] = []

        def fake_move_relative(direction, steps, speed_raw, acceleration_raw):
            calls.append(
                {
                    "direction": direction,
                    "steps": steps,
                    "speed_raw": speed_raw,
                    "acceleration_raw": acceleration_raw,
                }
            )

        monkeypatch.setattr(interpreter_actions, "_post_motor2_move_relative", fake_move_relative)

        src = """VERSION: 5
TASK:
  NAME 'Short motor jog'
  SET 'motor2' 'direction left'
  SET 'motor2' 'move 240 steps at 80 steps/s'
"""

        result = CqlInterpreter(mode="execute", quiet=True).run(src)

        assert result.ok is True
        assert calls == [{
            "direction": "left",
            "steps": 240,
            "speed_raw": 800_000,
            "acceleration_raw": None,
        }]

    def test_motor2_runtime_config_builds_volume_duration_plan(self):
        cfg = normalize_motor2_runtime_config(
            {
                "strokeSteps": 1000,
                "cycleVolumeLiters": 5,
                "maxStepsPerSecond": 1000,
                "defaultSpeedStepsPerSecond": 1000,
                "accelerationPercentPerSecond": 300,
                "limitMode": "reverse on limit",
                "startDirection": "left",
                "idleState": "deenergized",
                "deenergizeOnStop": True,
                "deenergizeOnStartup": True,
            }
        )

        plan = build_motor2_reciprocating_plan(
            cfg,
            volume_liters=50,
            duration_seconds=30,
        )

        assert plan.cycles == 10
        assert plan.steps == 1000
        assert plan.requested_steps_per_second == 667
        assert plan.effective_steps_per_second == 667
        assert plan.acceleration_percent_per_second == 300
        assert plan.limit_mode == "reverse_on_limit"
        assert plan.direction == "left"
        assert cfg.idle_state == "deenergized"
        assert cfg.deenergize_on_stop is True
        assert cfg.deenergize_on_startup is True
        assert cfg.stop_at_limit is True

    def test_motor2_volume_duration_reciprocating_calculates_cycles_and_speed(self, monkeypatch):
        reciprocate_calls: list[dict[str, object]] = []

        def fake_reciprocate(direction, steps, speed_raw, acceleration_raw, cycles, pause, limit_mode):
            reciprocate_calls.append(
                {
                    "direction": direction,
                    "steps": steps,
                    "speed_raw": speed_raw,
                    "acceleration_raw": acceleration_raw,
                    "cycles": cycles,
                    "pause": pause,
                    "limit_mode": limit_mode,
                }
            )

        monkeypatch.setattr(interpreter_actions, "_post_motor2_reciprocate", fake_reciprocate)

        src = """VERSION: 4
GOAL:
  SET NAME 'Test goal'
  SET 'motor 2' 'reciprocating motion'
  SET 'motor 2' 'stroke 1000 steps'
  SET 'motor 2' 'volume 50 l'
  SET 'motor 2' 'duration 30s'
  SET 'motor 2' 'acceleration 100%/s'
  SET 'motor 2' 'reverse on limit'
  SET 'motor 2' 'start left direction'
"""

        interp = CqlInterpreter(mode="execute", quiet=True)
        result = interp.run(src)

        assert result.ok is True
        assert reciprocate_calls == [
            {
                "direction": "left",
                "steps": 1000,
                "speed_raw": 6_670_000,
                "acceleration_raw": 66_700,
                "cycles": 10,
                "pause": 0.0,
                "limit_mode": "reverse_on_limit",
            }
        ]

    def test_motor2_volume_start_without_direction_defaults_left(self, monkeypatch):
        reciprocate_calls: list[dict[str, object]] = []

        def fake_reciprocate(direction, steps, speed_raw, acceleration_raw, cycles, pause, limit_mode):
            reciprocate_calls.append(
                {
                    "direction": direction,
                    "steps": steps,
                    "speed_raw": speed_raw,
                    "cycles": cycles,
                    "limit_mode": limit_mode,
                }
            )

        monkeypatch.setattr(interpreter_actions, "_post_motor2_reciprocate", fake_reciprocate)

        src = """VERSION: 4
GOAL:
  SET NAME 'Test goal'
  SET 'motor 2' 'reciprocating motion'
  SET 'motor 2' 'stroke 1000 steps'
  SET 'motor 2' 'volume 50 l'
  SET 'motor 2' 'duration 30s'
  SET 'motor 2' 'reverse on limit'
  SET 'motor 2' 'start'
"""

        interp = CqlInterpreter(mode="execute", quiet=True)
        result = interp.run(src)

        assert result.ok is True
        assert reciprocate_calls == [
            {
                "direction": "left",
                "steps": 1000,
                "speed_raw": 6_670_000,
                "cycles": 10,
                "limit_mode": "reverse_on_limit",
            }
        ]

    def test_motor2_acceleration_percent_above_100_is_preserved(self, monkeypatch):
        move_calls: list[dict[str, object]] = []

        def fake_move_relative(direction, steps, speed_raw, acceleration_raw):
            move_calls.append(
                {
                    "direction": direction,
                    "steps": steps,
                    "speed_raw": speed_raw,
                    "acceleration_raw": acceleration_raw,
                }
            )

        monkeypatch.setattr(interpreter_actions, "_post_motor2_move_relative", fake_move_relative)

        src = """VERSION: 4
GOAL:
  SET NAME 'Test goal'
  SET 'motor 2' 'direction left'
  SET 'motor 2' 'acceleration 200%/s'
  SET 'motor 2' '1000 steps/s'
"""

        interp = CqlInterpreter(mode="execute", quiet=True)
        result = interp.run(src)

        assert result.ok is True
        assert move_calls == [
            {
                "direction": "left",
                "steps": 1000,
                "speed_raw": 10_000_000,
                "acceleration_raw": 200_000,
            }
        ]

    def test_repeat_stop_is_accepted_in_expanded_oql_repeat_blocks(self):
        src = """VERSION: 4
GOAL:
  SET NAME 'Test goal'
  REPEAT 3:
    SET 'loop marker' 'before stop'
    REPEAT STOP
    SET 'loop marker' 'after stop'
"""

        interp = CqlInterpreter(mode="dry-run", quiet=True)
        result = interp.run(src)

        assert result.ok is True
        assert not result.errors

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

    def test_execute_mode_does_not_seed_default_sensor_mocks(self):
        interp = CqlInterpreter(mode="execute", quiet=True)
        assert "AI01" not in interp.sensor_values
        assert "AI02" not in interp.sensor_values

    def test_oql_val_evaluates_registered_min_max_thresholds(self):
        src = """VERSION: 5
TASK:
  NAME 'Test goal'
  MIN 'AI01' '-11.0 mbar'
  MAX 'AI01' '-9.0 mbar'
  VAL 'AI01' 'mbar'
"""
        interp = CqlInterpreter(mode="execute", quiet=True, sensor_values={"AI01": -10.0})
        result = interp.run(src)

        assert result.ok is True
        assert result.failed == 0
        assert interp.vars.get("AI01") == -10.0

    def test_oql_val_fails_when_registered_threshold_is_violated(self):
        src = """VERSION: 5
TASK:
  NAME 'Test goal'
  MIN 'AI01' '-11.0 mbar'
  MAX 'AI01' '-9.0 mbar'
  VAL 'AI01' 'mbar'
"""
        interp = CqlInterpreter(mode="execute", quiet=True, sensor_values={"AI01": -12.0})
        result = interp.run(src)

        assert result.ok is False
        assert result.failed >= 1
        assert any("outside" in err for err in result.errors)

    def test_oql_val_fails_without_real_execute_value(self, monkeypatch):
        src = """VERSION: 5
TASK:
  NAME 'Test goal'
  MIN 'AI01' '-11.0 mbar'
  MAX 'AI01' '-9.0 mbar'
  VAL 'AI01' 'mbar'
"""
        interp = CqlInterpreter(mode="execute", quiet=True)
        monkeypatch.setattr(interp, "_refresh_sensors_from_firmware", lambda: None)
        result = interp.run(src)

        assert result.ok is False
        assert result.failed >= 1
        assert any("missing real sensor/variable value" in err for err in result.errors)

    def test_oql_val_without_threshold_missing_value_is_warning_not_fail(self, monkeypatch):
        # VAL bez zarejestrowanego progu = zapis do protokołu. Brak odczytu w
        # execute nie może oblać celu (nie ma bramki) — tylko ostrzeżenie.
        src = """VERSION: 5
TASK:
  NAME 'Test goal'
  SET 'Operator' 'confirm'
  VAL 'operator.result'
"""
        interp = CqlInterpreter(mode="execute", quiet=True)
        monkeypatch.setattr(interp, "_refresh_sensors_from_firmware", lambda: None)
        result = interp.run(src)

        assert result.ok is True, result.errors
        assert any("operator.result" in w for w in result.warnings)

    def test_oql_val_dry_run_automocks_missing_named_param(self):
        src = """VERSION: 5
TASK:
  NAME 'Test goal'
  RANGE 'cisnienie' '4.0 mbar' .. '6.0 mbar'
  VAL 'cisnienie' 'mbar'
"""
        interp = CqlInterpreter(mode="dry-run", quiet=True)
        result = interp.run(src)

        assert result.ok is True, result.errors
        assert float(result.variables.get("cisnienie")) == 5.0

    def test_oql_if_comparative_evaluates_in_execute(self):
        src = """VERSION: 5
TASK:
  NAME 'Test goal'
  IF 'cisnienie' > '1.5 bar'
"""
        interp = CqlInterpreter(mode="execute", quiet=True, sensor_values={"cisnienie": 2.0})
        result = interp.run(src)
        assert result.ok is True, result.errors

        interp = CqlInterpreter(mode="execute", quiet=True, sensor_values={"cisnienie": 1.0})
        result = interp.run(src)
        assert result.ok is False
        assert any("cisnienie" in err for err in result.errors)

    def test_oql_if_missing_value_fails_in_execute(self, monkeypatch):
        src = """VERSION: 5
TASK:
  NAME 'Test goal'
  IF 'cisnienie' > '1.5 bar'
"""
        interp = CqlInterpreter(mode="execute", quiet=True)
        monkeypatch.setattr(interp, "_refresh_sensors_from_firmware", lambda: None)
        result = interp.run(src)

        assert result.ok is False
        assert any("missing real sensor/variable value" in err for err in result.errors)

    def test_oql_unevaluated_threshold_deferred_eval_execute_fails(self, monkeypatch):
        # Próg na parametrze, którego żaden VAL nie odczytał: w execute odroczona
        # ewaluacja na końcu GOAL-a nie znajduje realnej wartości → twardy błąd.
        src = """VERSION: 5
TASK:
  NAME 'Test goal'
  RANGE 'srednia' '95 mbar' .. '105 mbar'
  VAL 'inny_param' 'mbar'
"""
        interp = CqlInterpreter(mode="execute", quiet=True, sensor_values={"inny_param": 100.0})
        monkeypatch.setattr(interp, "_refresh_sensors_from_firmware", lambda: None)
        result = interp.run(src)

        assert result.ok is False
        assert any("srednia" in err and "missing real" in err for err in result.errors)

    def test_oql_unevaluated_threshold_deferred_eval_dryrun_mocks(self):
        # W dry-run odroczona ewaluacja automockuje brakującą wartość do środka
        # zakresu — scenarusz deweloperski przechodzi bez sprzętu.
        src = """VERSION: 5
TASK:
  NAME 'Test goal'
  RANGE 'srednia' '95 mbar' .. '105 mbar'
  VAL 'inny_param' 'mbar'
"""
        interp = CqlInterpreter(mode="dry-run", quiet=True)
        result = interp.run(src)

        assert result.ok is True, result.errors
        assert float(interp.vars.get("srednia")) == 100.0

    def test_oql_thresholds_do_not_leak_between_goals(self):
        src = """VERSION: 5
TASK:
  NAME 'Pierwszy'
  RANGE 'p1' '1 mbar' .. '2 mbar'
  VAL 'p1' 'mbar'
TASK:
  NAME 'Drugi'
  VAL 'p1' 'mbar'
"""
        interp = CqlInterpreter(mode="dry-run", quiet=True)
        result = interp.run(src)
        assert result.ok is True, result.errors

    def test_oql_parse_errors_fail_run(self):
        src = """VERSION: 5
TASK:
  NAME 'Test goal'
  NIEZNANA_KOMENDA 'x'
"""
        interp = CqlInterpreter(mode="dry-run", quiet=True)
        result = interp.run(src)

        assert result.ok is False
        assert any("NIEZNANA_KOMENDA" in err for err in result.errors)

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
        assert result["status"] == 503
        assert result["error_code"] == "C2004-HW-0012"
        assert result["detail"] == "Required hardware is unavailable"
        assert "allowed raster" not in str(result)

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
