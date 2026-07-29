from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "refactor_audit.py"
SPEC = importlib.util.spec_from_file_location("refactor_audit", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
refactor_audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(refactor_audit)


def test_python_audit_detects_route_env_and_raw_failures(tmp_path: Path) -> None:
    source = tmp_path / "api.py"
    source.write_text(
        """
import os
from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.get('/items')
def items() -> dict[str, Any]:
    value = os.getenv('ITEM')
    try:
        raise ValueError(value)
    except Exception:
        return {'ok': False}
""",
        encoding="utf-8",
    )
    report = {
        "parse_failures": [],
        "public_routes": [],
        "routes_returning_dict_any": [],
        "routes_with_generic_response": [],
        "routes_with_false_success_at_http_200": [],
        "environment_reads_outside_settings": [],
        "raw_exceptions": [],
        "broad_exception_handlers": [],
    }

    refactor_audit._audit_python(source, tmp_path, report)

    assert len(report["public_routes"]) == 1
    assert len(report["routes_returning_dict_any"]) == 1
    assert len(report["routes_with_generic_response"]) == 1
    assert len(report["routes_with_false_success_at_http_200"]) == 1
    assert len(report["environment_reads_outside_settings"]) == 1
    assert report["raw_exceptions"][0]["exception"] == "ValueError"
    assert report["broad_exception_handlers"][0]["exception"] == "Exception"


def test_settings_module_is_allowed_to_read_environment(tmp_path: Path) -> None:
    source = tmp_path / "settings.py"
    source.write_text("import os\nVALUE = os.environ.get('VALUE')\n", encoding="utf-8")
    report = {
        "parse_failures": [],
        "public_routes": [],
        "routes_returning_dict_any": [],
        "routes_with_generic_response": [],
        "routes_with_false_success_at_http_200": [],
        "environment_reads_outside_settings": [],
        "raw_exceptions": [],
        "broad_exception_handlers": [],
    }

    refactor_audit._audit_python(source, tmp_path, report)

    assert report["environment_reads_outside_settings"] == []
