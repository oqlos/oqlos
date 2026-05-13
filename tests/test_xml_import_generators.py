from oqlos.tools.xml_import.generators import generate_cql
from oqlos.tools.xml_import.models import DeviceReport, Operation, Output, SensorParam, TestRun as XmlTestRun


def test_generate_cql_uses_canonical_set_syntax():
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

    cql = generate_cql(report)

    assert "SET 'pompa' '5 l'" in cql
    assert "SET 'sprężarka' '120 l/min'" in cql
    assert "SET 'BO 06' '1'" in cql
    assert "SET 'Potwierdz gotowosc' '1'" in cql
    assert "SET [" not in cql
