from oqlos.core.state import StateManager
from oqlos.utils.hui_scenario import register_hui_test_scenario


def test_register_hui_test_scenario_adds_ts_c20_once():
    state = StateManager()
    register_hui_test_scenario(state)
    assert "ts-c20" in state.scenarios
    first = state.scenarios["ts-c20"]
    assert first.protocol == "oql"
    register_hui_test_scenario(state)
    assert state.scenarios["ts-c20"] is first
