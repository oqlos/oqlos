"""Tests for runtime command payload normalization."""

from oqlos.api import state as _mod


def test_extract_scenario_id_accepts_frontend_and_cli_keys():
    assert _mod._extract_scenario_id({'scenarioId': 'one'}) == 'one'
    assert _mod._extract_scenario_id({'scenario_id': 'two'}) == 'two'
    assert _mod._extract_scenario_id({'scenario_context_id': 'three'}) == 'three'


def test_extract_inline_dsl_accepts_content_and_direct_fields():
    assert _mod._extract_inline_dsl({'content': {'dsl': 'GOAL: A\nSET "zawor 1" "ON"'}}) == 'GOAL: A\nSET "zawor 1" "ON"'
    assert _mod._extract_inline_dsl({'dsl': 'GOAL: A\nSET "zawor 1" "ON"'}) == 'GOAL: A\nSET "zawor 1" "ON"'
    assert _mod._extract_inline_dsl({'dsl_code': 'GOAL: A\nSET "zawor 1" "ON"'}) == 'GOAL: A\nSET "zawor 1" "ON"'
