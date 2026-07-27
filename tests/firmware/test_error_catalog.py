"""Regression: every `code=`/`issue_code=` literal in known source locations is
registered in the OqlIssue catalog, and docs/ERROR_CODES.md stays in sync with
oqlos/errors/catalog.py.
"""

from __future__ import annotations

import re
from pathlib import Path

from oqlos.errors.catalog import ISSUE_CATALOG, matches_known_pattern
from oqlos.tools.gen_error_docs import DOC_PATH, generate_markdown

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOCTOR_DIR = _REPO_ROOT / "oqlos" / "tools" / "hardware_diagnose"
_CODE_SOURCE_PATHS = [
    *sorted(_DOCTOR_DIR.glob("doctor_*.py")),
    _REPO_ROOT / "oqlos" / "hardware" / "diagnosis_device_actions.py",
    _REPO_ROOT / "oqlos" / "api" / "oql_mqtt.py",
    _REPO_ROOT / "oqlos" / "api" / "hardware_diagnosis_routes.py",
    _REPO_ROOT / "oqlos" / "api" / "_hw3_cqrs.py",
    _REPO_ROOT / "oqlos" / "api" / "hardware_modbus_channels.py",
    _REPO_ROOT / "oqlos" / "api" / "hardware_modbus_routes.py",
    _REPO_ROOT / "oqlos" / "api" / "hardware_modbus_waveshare.py",
    _REPO_ROOT / "oqlos" / "api" / "hardware_peripherals_routes.py",
    _REPO_ROOT / "oqlos" / "api" / "hardware_probe.py",
    _REPO_ROOT / "oqlos" / "api" / "hardware_runtime.py",
    _REPO_ROOT / "oqlos" / "api" / "plugins.py",
    _REPO_ROOT / "oqlos" / "hardware" / "plugin_gateway.py",
    _REPO_ROOT / "oqlos" / "hardware" / "usb_diagnostics.py",
]
_CODE_LITERAL = re.compile(r'code\s*=\s*"([a-z0-9_]+)"')
_CODE_FSTRING = re.compile(r'code\s*=\s*f"([a-z0-9_{}]+)"')
_CODE_DICT_LITERAL = re.compile(r'"(?:code|issue_code)"\s*:\s*"([a-z0-9_]+)"')


def _codes_used_in_source() -> set[str]:
    codes: set[str] = set()
    for path in _CODE_SOURCE_PATHS:
        codes.update(_CODE_LITERAL.findall(path.read_text()))
        codes.update(_CODE_DICT_LITERAL.findall(path.read_text()))
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
    assert DOC_PATH.exists(), "docs/ERROR_CODES.md missing — run `python -m oqlos.tools.gen_error_docs`"
    assert DOC_PATH.read_text() == generate_markdown(), (
        "docs/ERROR_CODES.md is stale — run `python -m oqlos.tools.gen_error_docs`"
    )


def test_every_repair_template_has_a_hint_or_is_manual_only():
    for defn in ISSUE_CATALOG.values():
        if defn.repair is None:
            continue
        assert defn.repair.id, f"{defn.code}: repair.id must not be empty"
