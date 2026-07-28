from oqlos.tools.xml_import.generators import generate_cql, generate_oql
from oqlos.tools.xml_import.models import DeviceReport, Operation, Output, SensorParam, TestRun as XmlTestRun


def test_generate_oql_uses_canonical_set_syntax():
    report = DeviceReport(report_id="demo", df_name="Maska", dt_name="PSS")
    operation = Operation(
        op_id="op#001",
        lp="1.1",
        name="Sterowanie",
        outputs=[
            Output(name="pump", value="5l"),
            Output(name="compressor", value="120"),
            Output(name="BO 06", value="on"),
        ],
        params=[
            SensorParam(sensor="operator", description="Potwierdz gotowosc", mode="on"),
        ],
    )
    report.test_runs.append(XmlTestRun(tr_id="tr#001", name="Test", operations=[operation]))

    oql = generate_oql(report)

    assert oql.startswith("VERSION: 5\n")
    assert "SET 'pompa' '5 l'" in oql
    assert "SET 'sprężarka' '120 l/min'" in oql
    assert "SET 'BO 06' '1'" in oql
    assert "TASK:\n  NAME 'Sterowanie'" in oql
    assert "PROMPT 'Potwierdz gotowosc'" in oql
    assert "TASK TITLE" not in oql
    assert "SET [" not in oql
    assert generate_cql(report) == oql
