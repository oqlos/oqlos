"""WAIT_UNTIL: v6 TASK precondition that polls a sensor until it is in range."""

from __future__ import annotations

import pytest
from oqlos.core.base import StepStatus
from oqlos.core.interpreter import OqlInterpreter
from oqlos.core.oql_parser import parse_oql
from oqlos.models.dsl_models import OqlAction

from oqlos.core import _interpreter_actions

SCENARIO = """VERSION: 6
SCENARIO: Ciśnienie zadane
TASK:
  NAME 'Ustawienie ciśnienia 30 mbar'
  SET 'pompa 1' '1'
  WAIT_UNTIL 'cn' '28 mbar' .. '32 mbar' EVERY '1 s' TIMEOUT '10 s'
TEST_STEP:
  NAME 'Pomiar'
  VAL 'cn' 'mbar'
  RANGE 'cn' '25 mbar' .. '35 mbar'
  PASS 'cn' 'ok'
  FAIL 'cn' 'nok'
"""


def _wait_until(rest: str):
    doc = parse_oql(f"VERSION: 6\nTASK:\n  NAME 'a'\n  WAIT_UNTIL {rest}\n")
    return doc, [cmd for block in doc.goals() for cmd in block.cmds if cmd.cmd == "WAIT_UNTIL"]


def test_wait_until_is_allowed_in_a_v6_task() -> None:
    doc = parse_oql(SCENARIO)
    assert doc.errors == []
    cmd = next(c for b in doc.goals() for c in b.cmds if c.cmd == "WAIT_UNTIL")
    assert {k: cmd.args[k] for k in ("sensor", "min", "max", "unit", "every_ms", "timeout_ms")} == {
        "sensor": "cn", "min": 28, "max": 32, "unit": "mbar", "every_ms": 1000, "timeout_ms": 10000,
    }


def test_wait_until_defaults_every_capped_by_timeout() -> None:
    assert _wait_until("'cn' '28' .. '32' TIMEOUT '10 s'")[1][0].args["every_ms"] == 1000
    assert _wait_until("'cn' '28' .. '32' TIMEOUT '500 ms'")[1][0].args["every_ms"] == 500
    assert _wait_until("'cn' '28' .. '32' TIMEOUT '2 s' EVERY '200 ms'")[1][0].args["every_ms"] == 200


@pytest.mark.parametrize(
    ("rest", "message"),
    [
        ("'cn' '28 mbar' .. '32 mbar' EVERY '1 s'", "WAIT_UNTIL wymaga TIMEOUT"),
        ("'cn' '28 mbar' '32 mbar' 'x' TIMEOUT '10 s'", "WAIT_UNTIL wymaga separatora"),
        ("'cn' '28 mbar' .. '32 mbar' EVERY '5 s' TIMEOUT '1 s'", "EVERY nie może"),
    ],
)
def test_wait_until_rejects_malformed_lines(rest: str, message: str) -> None:
    doc, _ = _wait_until(rest)
    assert any(message in error for error in doc.errors), doc.errors


def test_wait_until_does_not_satisfy_test_step_requirements() -> None:
    doc = parse_oql(
        "VERSION: 6\nTEST_STEP:\n  NAME 'a'\n  WAIT_UNTIL 'cn' '28' .. '32' TIMEOUT '1 s'\n"
        "  PASS 'cn' 'ok'\n  FAIL 'cn' 'nok'\n"
    )
    joined = "\n".join(doc.errors)
    assert "TEST_STEP wymaga kryterium" in joined
    assert "TEST_STEP wymaga odczytu VAL lub GET" in joined


def test_wait_until_dry_run_is_simulated() -> None:
    interp = OqlInterpreter(mode="dry-run", quiet=True)
    result = interp.run(SCENARIO.replace("  VAL 'cn' 'mbar'\n", "  SET 'cn' '30'\n  VAL 'cn' 'mbar'\n"))
    assert not any("WAIT_UNTIL" in str(error) for error in interp.errors)
    assert result.ok is True, interp.errors


class _FakeInterp:
    mode = "execute"
    _skip_waits = False

    def __init__(self, readings: list[float]) -> None:
        self.readings = list(readings)
        self.sensor_values: dict[str, float] = {}
        self.errors: list[str] = []
        self.refreshes = 0
        self.vars = type("V", (), {"set": lambda _s, k, v: None})()
        self.out = type("O", (), {"step": lambda *_: None, "warn": lambda *_: None, "error": lambda *_: None})()

    def _refresh_sensors_from_firmware(self) -> None:
        self.refreshes += 1
        self.sensor_values["cn"] = self.readings.pop(0) if self.readings else self.sensor_values["cn"]

    @staticmethod
    def _coerce_float(value):
        return None if value is None else float(value)


def _run(interp: _FakeInterp, monkeypatch, timeout_ms: int = 10000) -> StepStatus:
    clock = {"t": 0.0}
    monkeypatch.setattr(_interpreter_actions.time, "monotonic", lambda: clock["t"])
    monkeypatch.setattr(_interpreter_actions, "_wait_until_sleep", lambda s: clock.__setitem__("t", clock["t"] + s))
    act = OqlAction(kind="wait_until", target="cn", args=f"28|32|1000|{timeout_ms}|mbar", raw="WAIT_UNTIL …")
    return _interpreter_actions.ACTION_HANDLERS["wait_until"](interp, act)


def test_wait_until_execute_polls_fresh_readings_until_in_range(monkeypatch) -> None:
    interp = _FakeInterp([5.0, 20.0, 29.5])
    assert _run(interp, monkeypatch) == StepStatus.PASSED
    assert interp.refreshes == 3
    assert interp.errors == []


def test_wait_until_execute_times_out_as_error(monkeypatch) -> None:
    interp = _FakeInterp([10.0])
    assert _run(interp, monkeypatch, timeout_ms=2500) == StepStatus.FAILED
    assert interp.refreshes == 4
    assert interp.errors and interp.errors[0].startswith("WAIT_UNTIL timeout after 2500 ms: cn=10.0")
