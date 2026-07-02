from oqlos.core.cql_parser import parse_cql, validate_cql


CQL_SIMPLE = """SCENARIO: Test

GOAL: Pompa
  SET 'pompa' '5 bar'
"""


def test_parse_cql_smoke():
    doc = parse_cql(CQL_SIMPLE)
    assert doc.metadata.scenario_name == "Test"
    assert len(doc.goals) == 1
    assert doc.goals[0].name == "Pompa"


def test_validate_cql_smoke():
    doc = parse_cql(CQL_SIMPLE)
    issues = validate_cql(doc)
    assert issues == []
