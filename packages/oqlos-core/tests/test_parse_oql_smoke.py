from oqlos.core.oql_document import parse_oql_document, validate_oql_document


OQL_SIMPLE = """SCENARIO: Test

GOAL: Pompa
  SET 'pompa' '5 bar'
"""


def test_parse_oql_smoke():
    doc = parse_oql_document(OQL_SIMPLE)
    assert doc.metadata.scenario_name == "Test"
    assert len(doc.goals) == 1
    assert doc.goals[0].name == "Pompa"


def test_validate_oql_smoke():
    doc = parse_oql_document(OQL_SIMPLE)
    issues = validate_oql_document(doc)
    assert issues == []
