from __future__ import annotations

from oqlos.core.cql_parser import parse_cql
from oqlos.core.interpreter import CqlInterpreter


def test_block_if_else_error_attaches_to_else_branch() -> None:
    src = """GOAL: Demo
  IF 'AI01' < '0.60'
    ELSE ERROR 'Too low'
  ENDIF
"""

    doc = parse_cql(src)
    action = doc.goals[0].steps[0].actions[0]

    assert action.kind == "if_block"
    assert action.then_actions == []
    assert [child.kind for child in action.else_actions] == ["else"]


def test_comment_only_if_block_does_not_capture_endif() -> None:
    src = """GOAL: Demo
  IF 'Timer' <= '7.0'
    # success path marker
  ENDIF
"""

    doc = parse_cql(src)
    action = doc.goals[0].steps[0].actions[0]

    assert action.kind == "if_block"
    assert action.then_actions == []
    assert action.else_actions == []


def test_oql_dry_run_supports_api_assert_shell_and_if_fail() -> None:
    src = """GOAL: Diagnostics
  EXPECT_DEVICE "/dev/ttyACM0" "CH340" "Modbus RTU"
  API_GET "/api/v1/hardware/health"
  ASSERT_STATUS 200
  ASSERT_JSON "mode" "real"
  GET_SENSOR "nc-sensor"
  ASSERT_SENSOR "nc-sensor" ">" "0"
  SET "zawor NC" "ON"
  ASSERT_VALVE "valve-nc" "True"
  IF_FAIL "modbus" THEN
    LOG "This should stay skipped in dry-run"
  END
GOAL: Report
  API_GET "/api/v1/state"
  SAVE_JSON "state"
  SHELL_EXPORT "HARDWARE_OK" "true"
"""

    interp = CqlInterpreter(mode="dry-run", quiet=True)
    result = interp.run(src)

    assert result.ok is True
    assert interp.vars.get("HARDWARE_OK") == "true"
    assert interp.vars.get("shell_exports") == {"HARDWARE_OK": "true"}
    assert isinstance(interp.vars.get("state"), dict)