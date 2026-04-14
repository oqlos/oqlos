#!/usr/bin/env python3
"""XML parser for c10 test reports."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .models import DeviceReport, Operation, Output, SensorParam, TestRun
from ._utils import FALLBACK_SORT_ORDINAL


def parse_xml(xml_path: Path) -> DeviceReport:
    """Parse c10 XML report file into DeviceReport."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    report_id = root.attrib.get("id", xml_path.stem)

    # Collect all vars into a flat dict
    vars_: dict[str, str] = {}
    for var_el in root.findall("var"):
        vid = var_el.attrib.get("id", "")
        vars_[vid] = (var_el.text or "").strip()

    report = DeviceReport(report_id=report_id)
    _populate_report_fields(report, vars_)
    _parse_intervals(report, vars_)

    # Test runs: dt#tr#NNN
    tr_ids = set()
    for key in vars_:
        m = re.match(r"^dt#tr#(\d{3})#", key)
        if m:
            tr_ids.add(m.group(1))

    for tr_num in sorted(tr_ids):
        tr = _parse_test_run(report, vars_, tr_num)
        report.test_runs.append(tr)

    return report


def _populate_report_fields(report: DeviceReport, vars_: dict[str, str]) -> None:
    """Fill scalar fields on the report from the vars dict."""
    report.date = vars_.get("date", "")
    report.result = vars_.get("result", "")
    report.dt_name = vars_.get("dt#name", "")
    report.dt_manufacturer = vars_.get("dt#manufact", "")
    report.dt_dfId = vars_.get("dt#dfId", "")
    report.df_name = vars_.get("df#name", "")
    report.dv_id = vars_.get("dv", "")
    report.dv_number = vars_.get("dv#number", "")
    report.dv_barcode = vars_.get("dv#barcode", "")
    report.dv_csId = vars_.get("dv#csId", "")
    report.cs_name = vars_.get("cs#name1", "")
    report.cs_city = vars_.get("cs#city", "")
    report.cs_street = vars_.get("cs#street", "")
    report.cs_contact = vars_.get("cs#contact", "")
    report.ws_name = vars_.get("ws#name1", "")
    report.ws_city = vars_.get("ws#city", "")


def _parse_intervals(report: DeviceReport, vars_: dict[str, str]) -> None:
    """Parse interval definitions from dt#tt# and df#tt# prefixes."""
    for prefix in ("dt#tt#", "df#tt#"):
        for key, val in vars_.items():
            m = re.match(rf"^{re.escape(prefix)}(\d{{3}})#name$", key)
            if m:
                tt_id = f"tt#{m.group(1)}"
                period_key = f"{prefix}{m.group(1)}#period"
                report.intervals[tt_id] = {
                    "name": val,
                    "period": int(vars_.get(period_key, "0")),
                }


def _parse_test_run(report: DeviceReport, vars_: dict[str, str], tr_num: str) -> TestRun:
    """Parse a single test run and its operations."""
    pfx = f"dt#tr#{tr_num}"
    tr = TestRun(
        tr_id=f"tr#{tr_num}",
        name=vars_.get(f"{pfx}#name", ""),
        lp=vars_.get(f"{pfx}#lp", ""),
        result=vars_.get(f"{pfx}#result", ""),
    )
    # Which intervals does this test run apply to?
    for tt_id in report.intervals:
        for variant_key in (f"{pfx}#df#{tt_id}#do", f"{pfx}#{tt_id}#do"):
            if vars_.get(variant_key, "") == "on":
                tr.do_intervals.append(tt_id)
                break

    # Operations: dt#tr#NNN#op#MMM
    op_ids = set()
    for key in vars_:
        m2 = re.match(rf"^{re.escape(pfx)}#op#(\d{{3}})#", key)
        if m2:
            op_ids.add(m2.group(1))

    for op_num in sorted(op_ids):
        op = _parse_operation(report, vars_, pfx, op_num)
        tr.operations.append(op)

    # Sort operations by lp (ordinal)
    def sort_key(op: Operation):
        parts = op.lp.split(".")
        return tuple(int(x) for x in parts if x.isdigit()) or (FALLBACK_SORT_ORDINAL,)
    tr.operations.sort(key=sort_key)
    return tr


def _parse_operation(report: DeviceReport, vars_: dict[str, str], pfx: str, op_num: str) -> Operation:
    """Parse a single operation within a test run."""
    opfx = f"{pfx}#op#{op_num}"
    op = Operation(op_id=f"op#{op_num}")
    op.lp = vars_.get(f"{opfx}#lp", "")
    op.lp_start = vars_.get(f"{opfx}#lpStart", "")
    op.name = vars_.get(f"{opfx}#name", "")
    op.display_l1 = vars_.get(f"{opfx}#dspl#L01", "")
    op.display_l2 = vars_.get(f"{opfx}#dspl#L02", "")
    op.alarm_l2 = vars_.get(f"{opfx}#dsplAlrm#L02", "")
    op.alarm_l3 = vars_.get(f"{opfx}#dsplAlrm#L03", "")
    op.result = vars_.get(f"{opfx}#result", "")

    # Outputs
    for key, val in vars_.items():
        m3 = re.match(rf"^{re.escape(opfx)}#out#(\w+)$", key)
        if m3:
            op.outputs.append(Output(name=m3.group(1), value=val))

    # Params (sensors + timer + operator)
    _parse_operation_params(op, vars_, opfx)

    # Interval applicability
    for tt_id in report.intervals:
        for variant_key in (f"{opfx}#df#{tt_id}#do", f"{opfx}#{tt_id}#do"):
            if vars_.get(variant_key, "") == "on":
                op.do_intervals.append(tt_id)
                break

    return op


def _parse_operation_params(op: Operation, vars_: dict[str, str], opfx: str) -> None:
    """Parse sensor parameters for an operation."""
    param_sensors = set()
    for key in vars_:
        m4 = re.match(rf"^{re.escape(opfx)}#prm#(\w+)#", key)
        if m4:
            param_sensors.add(m4.group(1))

    for sensor in sorted(param_sensors):
        spfx = f"{opfx}#prm#{sensor}"
        mode = vars_.get(f"{spfx}#mode", "Off")
        p = SensorParam(
            sensor=sensor,
            description=vars_.get(f"{spfx}#dsc", ""),
            unit=vars_.get(f"{spfx}#unit", ""),
            mode=mode,
            result=vars_.get(f"{spfx}#result", ""),
            save=vars_.get(f"{spfx}#save", "Off") == "On",
            editable=vars_.get(f"{spfx}#editable", "") == "on",
            type_=vars_.get(f"{spfx}#type", ""),
        )
        for num_field in ("min", "max", "value"):
            raw = vars_.get(f"{spfx}#{num_field}", "")
            if raw.strip():
                try:
                    setattr(p, f"{num_field}_val" if num_field != "value" else "value",
                            float(raw.strip()))
                except ValueError:
                    if num_field == "value":
                        p.value_str = raw.strip()
        op.params.append(p)
