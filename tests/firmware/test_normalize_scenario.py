"""Tests for scenario row normalization functions.

Covers:
- _extract_id: ID extraction and validation
- _extract_display_fields: field resolution with fallbacks
- _extract_goals: content parsing delegation
- _normalize_scenario_row: full pipeline (orchestrator)
- _compute_slug: slug generation
"""

import pytest

from oqlos.api.scenarios import (
    _extract_id,
    _extract_display_fields,
    _extract_goals,
    _normalize_scenario_row,
    _compute_slug,
)
from oqlos.models.scenario import Scenario, Goal


# ===== _extract_id =============================================================

class TestExtractId:
    def test_valid_id(self):
        assert _extract_id({"id": "ts-c20"}) == "ts-c20"

    def test_strips_whitespace(self):
        assert _extract_id({"id": "  ts-c20  "}) == "ts-c20"

    def test_missing_id_returns_none(self):
        assert _extract_id({}) is None

    def test_empty_string_returns_none(self):
        assert _extract_id({"id": ""}) is None

    def test_none_value_returns_none(self):
        assert _extract_id({"id": None}) is None

    def test_numeric_id_converted_to_str(self):
        assert _extract_id({"id": 42}) == "42"


# ===== _extract_display_fields =================================================

class TestExtractDisplayFields:
    def test_all_fields_present(self):
        item = {
            "name": "C20 Test",
            "description": "Pressure test",
            "device": "PSS-7000",
            "protocol": "c20-protocol",
            "code": "C20",
            "slug": "c20-test",
        }
        fields = _extract_display_fields(item, "ts-c20")
        assert fields["name"] == "C20 Test"
        assert fields["description"] == "Pressure test"
        assert fields["device"] == "PSS-7000"
        assert fields["protocol"] == "c20-protocol"
        assert fields["code"] == "C20"
        assert fields["slug"] == "c20-test"

    def test_name_fallback_to_title(self):
        fields = _extract_display_fields({"title": "From Title"}, "sid")
        assert fields["name"] == "From Title"

    def test_name_fallback_to_code(self):
        fields = _extract_display_fields({"code": "C20"}, "sid")
        assert fields["name"] == "C20"

    def test_name_fallback_to_sid(self):
        fields = _extract_display_fields({}, "ts-fallback")
        assert fields["name"] == "ts-fallback"

    def test_device_fallback_to_device_id(self):
        fields = _extract_display_fields({"device_id": "dev-123"}, "sid")
        assert fields["device"] == "dev-123"

    def test_protocol_fallback_to_protocol_id(self):
        fields = _extract_display_fields({"protocol_id": "proto-1"}, "sid")
        assert fields["protocol"] == "proto-1"

    def test_missing_optional_fields_default_empty(self):
        fields = _extract_display_fields({}, "sid")
        assert fields["description"] == ""
        assert fields["device"] == ""
        assert fields["protocol"] == ""
        assert fields["code"] is None


# ===== _extract_goals ==========================================================

class TestExtractGoals:
    def test_no_content_returns_empty(self):
        assert _extract_goals({}) == []

    def test_none_content_returns_empty(self):
        assert _extract_goals({"content": None}) == []

    def test_content_with_goals(self):
        item = {
            "content": {
                "goals": [
                    {
                        "id": "g1",
                        "name": "Goal 1",
                        "description": "desc",
                        "steps": [
                            {"id": "s1", "action": "SET_VALVE", "peripheral": "valve-nc", "value": 1}
                        ],
                    }
                ]
            }
        }
        goals = _extract_goals(item)
        assert len(goals) == 1
        assert goals[0].id == "g1"
        assert goals[0].name == "Goal 1"
        assert len(goals[0].steps) == 1
        assert goals[0].steps[0].action == "SET_VALVE"

    def test_content_without_goals_key(self):
        assert _extract_goals({"content": {"something": "else"}}) == []

    def test_content_non_dict(self):
        assert _extract_goals({"content": "plain string"}) == []


# ===== _compute_slug ===========================================================

class TestComputeSlug:
    def test_explicit_slug(self):
        assert _compute_slug({"slug": "my-slug"}, "name", "id") == "my-slug"

    def test_slug_from_code(self):
        assert _compute_slug({"code": "C20 Test!"}, "name", "id") == "c20-test"

    def test_slug_from_display_name(self):
        assert _compute_slug({}, "Pressure Test", "id") == "pressure-test"

    def test_slug_from_sid(self):
        assert _compute_slug({}, "", "ts-c20") == "ts-c20"

    def test_double_hyphens_collapsed(self):
        assert _compute_slug({"code": "a--b"}, "", "id") == "a-b"

    def test_strips_leading_trailing_hyphens(self):
        assert _compute_slug({"code": "!test!"}, "", "id") == "test"


# ===== _normalize_scenario_row (integration) ===================================

class TestNormalizeScenarioRow:
    def test_full_row(self):
        item = {
            "id": "ts-c20",
            "name": "C20 Pressure Test",
            "description": "Full pressure test scenario",
            "device": "PSS-7000",
            "protocol": "c20",
            "code": "C20",
            "content": {
                "goals": [
                    {
                        "id": "g1",
                        "name": "Prepare",
                        "steps": [{"id": "s1", "action": "SET_VALVE"}],
                    }
                ]
            },
        }
        scenario = _normalize_scenario_row(item)
        assert isinstance(scenario, Scenario)
        assert scenario.id == "ts-c20"
        assert scenario.name == "C20 Pressure Test"
        assert scenario.device == "PSS-7000"
        assert len(scenario.goals) == 1

    def test_minimal_row(self):
        scenario = _normalize_scenario_row({"id": "ts-1"})
        assert isinstance(scenario, Scenario)
        assert scenario.id == "ts-1"
        assert scenario.name == "ts-1"
        assert scenario.goals == []

    def test_missing_id_returns_none(self):
        assert _normalize_scenario_row({}) is None

    def test_empty_id_returns_none(self):
        assert _normalize_scenario_row({"id": ""}) is None

    def test_fallback_fields(self):
        item = {"id": "42", "title": "From Title", "device_id": "dev-x", "protocol_id": "p-1"}
        scenario = _normalize_scenario_row(item)
        assert scenario.name == "From Title"
        assert scenario.device == "dev-x"
        assert scenario.protocol == "p-1"
