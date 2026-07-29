"""Regression: every `code=`/`issue_code=` literal in known source locations is
registered in the OqlIssue catalog, and docs/ERROR_CODES.md stays in sync with
oqlos/errors/catalog.py.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from oqlos.errors.catalog import ISSUE_CATALOG, matches_known_pattern
from oqlos.errors.c2004_catalog_generated import (
    CATALOG,
    c2004_code_for_issue,
)
from oqlos.errors.fastapi_integration import _STATUS_CODE_MAP
from oqlos.tools.gen_error_docs import generate_markdown

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOC_PATH = _REPO_ROOT / "docs" / "ERROR_CODES.md"
_DOCTOR_DIR = _REPO_ROOT / "oqlos" / "tools" / "hardware_diagnose"
_CODE_SOURCE_PATHS = [
    *sorted(_DOCTOR_DIR.glob("doctor_*.py")),
    _REPO_ROOT / "oqlos" / "hardware" / "diagnosis_device_actions.py",
    _REPO_ROOT / "oqlos" / "api" / "oql_mqtt.py",
    _REPO_ROOT / "oqlos" / "api" / "hardware_diagnosis_routes.py",
    _REPO_ROOT / "oqlos" / "api" / "_hw3_cqrs.py",
    _REPO_ROOT / "oqlos" / "api" / "_hw3_peripheral.py",
    _REPO_ROOT / "oqlos" / "api" / "_hw3_system.py",
    _REPO_ROOT / "oqlos" / "api" / "editor.py",
    _REPO_ROOT / "oqlos" / "api" / "hardware_gateway.py",
    _REPO_ROOT / "oqlos" / "api" / "hardware_configuration_routes.py",
    _REPO_ROOT / "oqlos" / "api" / "hardware_modbus_channels.py",
    _REPO_ROOT / "oqlos" / "api" / "hardware_modbus_coil_test.py",
    _REPO_ROOT / "oqlos" / "api" / "hardware_modbus_routes.py",
    _REPO_ROOT / "oqlos" / "api" / "hardware_modbus_waveshare.py",
    _REPO_ROOT / "oqlos" / "api" / "hardware_peripherals_routes.py",
    _REPO_ROOT / "oqlos" / "api" / "hardware_probe.py",
    _REPO_ROOT / "oqlos" / "api" / "hardware_runtime.py",
    _REPO_ROOT / "oqlos" / "api" / "plugins.py",
    _REPO_ROOT / "oqlos" / "api" / "scenarios.py",
    _REPO_ROOT / "oqlos" / "hardware" / "plugin_gateway.py",
    _REPO_ROOT / "oqlos" / "hardware" / "usb_diagnostics.py",
    _REPO_ROOT / "oqlos" / "hardware" / "hui_readiness.py",
]
_CODE_LITERAL = re.compile(r'code\s*=\s*"([a-z0-9_]+)"')
_CODE_FSTRING = re.compile(r'code\s*=\s*f"([a-z0-9_{}]+)"')
_CODE_DICT_LITERAL = re.compile(r'"code"\s*:\s*"([a-z0-9_]+)"')
_ISSUE_CODE_DICT_LITERAL = re.compile(r'"issue_code"\s*:\s*"([a-z0-9_]+)"')


def _codes_used_in_source() -> set[str]:
    codes: set[str] = set()
    for path in _CODE_SOURCE_PATHS:
        codes.update(_CODE_LITERAL.findall(path.read_text()))
        codes.update(_CODE_DICT_LITERAL.findall(path.read_text()))
        codes.update(_ISSUE_CODE_DICT_LITERAL.findall(path.read_text()))
    return codes


def _fstring_code_templates_in_source() -> set[str]:
    """f-string codes like f"adapter_{adapter_id}_not_ok" -> "adapter_{adapter_id}_not_ok"."""
    templates: set[str] = set()
    for path in _CODE_SOURCE_PATHS:
        templates.update(_CODE_FSTRING.findall(path.read_text()))
    return templates


def test_every_doctor_fstring_code_matches_a_registered_pattern():
    templates = _fstring_code_templates_in_source()
    for template in templates:
        example = template.replace("{adapter_id}", "example-adapter")
        assert matches_known_pattern(example), (
            f"f-string code template {template!r} (e.g. {example!r}) has no matching "
            "CodePattern in oqlos/errors/catalog.py"
        )


def test_dynamic_plugin_health_issue_has_hardware_definition():
    from oqlos.errors.catalog import get_issue_definition

    definition = get_issue_definition("adapter_modbus-io_health_not_ok")

    assert definition is not None
    assert definition.domain == "hardware"
    assert definition.default_severity == "warning"


def test_every_source_code_is_registered_in_catalog():
    used = _codes_used_in_source()
    missing = used - set(ISSUE_CATALOG)
    assert not missing, f"codes used in source but missing from ISSUE_CATALOG: {sorted(missing)}"


def test_every_catalog_code_is_still_used_somewhere():
    """Catch stale catalog entries for codes no one raises anymore."""
    used = _codes_used_in_source()
    orphaned = set(ISSUE_CATALOG) - used
    assert not orphaned, f"catalog codes no longer used in source: {sorted(orphaned)}"


def test_error_codes_doc_is_up_to_date():
    assert _DOC_PATH.exists(), "docs/ERROR_CODES.md missing — run `python -m oqlos.tools.gen_error_docs`"
    assert _DOC_PATH.read_text() == generate_markdown(), (
        "docs/ERROR_CODES.md is stale — run `python -m oqlos.tools.gen_error_docs`"
    )


def test_every_repair_template_has_a_hint_or_is_manual_only():
    for defn in ISSUE_CATALOG.values():
        if defn.repair is None:
            continue
        assert defn.repair.id, f"{defn.code}: repair.id must not be empty"


def test_every_fixed_issue_maps_to_an_existing_public_code():
    dynamic_public_code_issues = {"remote_oql_execution_failed"}
    fallback = {
        code
        for code in ISSUE_CATALOG
        if c2004_code_for_issue(code) == "C2004-SYS-0000"
    }

    assert fallback == dynamic_public_code_issues
    assert all(
        c2004_code_for_issue(code) in CATALOG
        for code in set(ISSUE_CATALOG) - dynamic_public_code_issues
    )


def test_http_status_fallback_map_matches_public_catalog():
    mismatches = {
        status: (code, CATALOG[code].http_status)
        for status, code in _STATUS_CODE_MAP.items()
        if CATALOG[code].http_status != status
    }

    assert mismatches == {}


def test_literal_oqlos_error_status_matches_public_catalog():
    mismatches: list[str] = []
    for path in (_REPO_ROOT / "oqlos").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call_name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else ""
            )
            if call_name != "OqlosError":
                continue
            code = None
            status = None
            public_code = None
            if node.args and isinstance(node.args[0], ast.Constant):
                code = node.args[0].value
            for keyword in node.keywords:
                if keyword.arg == "code" and isinstance(keyword.value, ast.Constant):
                    code = keyword.value.value
                elif keyword.arg == "status_code" and isinstance(
                    keyword.value, ast.Constant
                ):
                    status = keyword.value.value
                elif keyword.arg == "public_code" and isinstance(
                    keyword.value, ast.Constant
                ):
                    public_code = keyword.value.value
            if not isinstance(code, str) or not isinstance(status, int):
                continue
            resolved = public_code or c2004_code_for_issue(code)
            entry = CATALOG.get(resolved)
            if entry is not None and entry.http_status != status:
                mismatches.append(
                    f"{path.relative_to(_REPO_ROOT)}:{node.lineno}: "
                    f"{code} -> {resolved} uses {status}, catalog={entry.http_status}"
                )

    assert mismatches == []
