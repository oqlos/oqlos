#!/usr/bin/env python3
"""Data models for XML to DSL conversion."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SensorParam:
    """Parameter measurement from an operation."""
    sensor: str          # AI01, AI02, AI03, timer, operator
    description: str = ""
    unit: str = ""
    mode: str = "Off"    # Off, minOk, maxOk, maxErr, inRangeOK, on
    min_val: float | None = None
    max_val: float | None = None
    value: float | None = None
    value_str: str | None = None
    result: str = ""
    save: bool = False
    editable: bool = False
    type_: str = ""      # end, ...


@dataclass
class Output:
    """Hardware output setting."""
    name: str       # pump, BO02, BO03, ...
    value: str      # Off, 5l, 10l, on


@dataclass
class Operation:
    """Single test operation (step)."""
    op_id: str           # op#000
    lp: str = ""         # ordinal like "1", "1.1", "2.2"
    lp_start: str = ""
    name: str = ""
    display_l1: str = ""
    display_l2: str = ""
    alarm_l2: str = ""
    alarm_l3: str = ""
    result: str = ""
    outputs: list[Output] = field(default_factory=list)
    params: list[SensorParam] = field(default_factory=list)
    do_intervals: list[str] = field(default_factory=list)


@dataclass
class TestRun:
    """A test run (scenario) within a device type."""
    tr_id: str           # tr#000
    name: str = ""
    lp: str = ""
    result: str = ""
    do_intervals: list[str] = field(default_factory=list)
    operations: list[Operation] = field(default_factory=list)


@dataclass
class DeviceReport:
    """Parsed device test report."""
    report_id: str       # dv00003/tst00000
    date: str = ""
    result: str = ""
    # Device type
    dt_name: str = ""
    dt_manufacturer: str = ""
    dt_dfId: str = ""
    # Device family
    df_name: str = ""
    # Device instance
    dv_id: str = ""
    dv_number: str = ""
    dv_barcode: str = ""
    dv_csId: str = ""
    # Customer
    cs_name: str = ""
    cs_city: str = ""
    cs_street: str = ""
    cs_contact: str = ""
    # Workshop
    ws_name: str = ""
    ws_city: str = ""
    # Intervals
    intervals: dict[str, dict] = field(default_factory=dict)
    # Test runs
    test_runs: list[TestRun] = field(default_factory=list)
