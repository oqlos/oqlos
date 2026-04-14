"""XML import tools — convert c10 XML test reports to DSL/CQL/JSON."""

from .models import DeviceReport, Operation, Output, SensorParam, TestRun
from .parser import parse_xml
from .generators import generate_cql, generate_dsl, generate_goals_json

__all__ = [
    "DeviceReport",
    "Operation",
    "Output",
    "SensorParam",
    "TestRun",
    "parse_xml",
    "generate_cql",
    "generate_dsl",
    "generate_goals_json",
]
