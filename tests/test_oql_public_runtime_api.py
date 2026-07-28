from oqlos.core.interpreter import OqlInterpreter
from oqlos.core.oql_document import parse_oql_document, validate_oql_document
from oqlos.models.dsl_models import OqlDocument
from oqlos.tools.oql_cli import run_single_command


def test_canonical_oql_runtime_symbols_parse_and_execute() -> None:
    source = (
        "VERSION: 5\n"
        "SCENARIO: Public API\n"
        "TASK:\n"
        "  NAME 'Start'\n"
        "  LOG 'ok'\n"
    )

    document = parse_oql_document(source, "public-api.oql")

    assert isinstance(document, OqlDocument)
    assert validate_oql_document(document) == []
    assert OqlInterpreter(mode="dry-run", quiet=True).run(source).ok is True


def test_public_oql_cli_executes_without_legacy_imports() -> None:
    result = run_single_command(
        "LOG 'public OQL CLI'",
        mode="dry-run",
        quiet=True,
        sensors={},
        firmware_url="http://localhost:8202",
        skip_waits=True,
    )

    assert result.ok is True
