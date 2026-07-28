"""XML import tools — convert c10 XML test reports to OQL and JSON."""

from .models import DeviceReport, Operation, Output, SensorParam, TestRun
from .parser import parse_xml
from .generators import generate_cql, generate_dsl, generate_goals_json, generate_oql
from ._utils import (
    FALLBACK_SORT_ORDINAL,
    OQL_V5,
    goal_block_header,
    goal_body_line,
    is_compressor_output,
    is_pump_output,
    normalize_flow_value,
    normalize_output_name,
    normalize_set_value,
    quote_oql_literal,
    scenario_document_header,
    slugify,
)

__all__ = [
    "DeviceReport",
    "Operation",
    "Output",
    "SensorParam",
    "TestRun",
    "parse_xml",
    "generate_oql",
    "generate_cql",
    "generate_dsl",
    "generate_goals_json",
    "FALLBACK_SORT_ORDINAL",
    "OQL_V5",
    "goal_block_header",
    "goal_body_line",
    "is_compressor_output",
    "is_pump_output",
    "normalize_flow_value",
    "normalize_output_name",
    "normalize_set_value",
    "quote_oql_literal",
    "scenario_document_header",
    "slugify",
]
