from oqlos.api import execution
from oqlos.core.state import StateManager


def test_runtime_source_is_registered_with_oql_protocol(monkeypatch):
    state = StateManager()
    monkeypatch.setattr(execution._ctrl, "state_manager", state)

    execution._register_dsl_scenario(
        "runtime-test",
        "VERSION: 5\n"
        "SCENARIO: Runtime\n"
        "TASK:\n"
        "  NAME 'Start'\n"
        "  LOG 'ok'\n",
    )

    assert state.scenarios["runtime-test"].protocol == "oql"
