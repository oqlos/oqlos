"""Problem-details contracts for the public scenario registry routes."""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from oqlos.api import scenarios
from oqlos.errors.fastapi_integration import install_oqlos_error_handler


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        scenarios._ctrl,
        "state_manager",
        SimpleNamespace(scenarios={}),
    )
    app = FastAPI()
    install_oqlos_error_handler(app)
    app.include_router(scenarios.router)
    return TestClient(app, raise_server_exceptions=False)


def test_missing_scenario_returns_safe_typed_not_found(client: TestClient) -> None:
    response = client.get(
        "/api/v1/scenarios/password=hunter2",
        headers={"X-Correlation-ID": "cor-scenario-missing"},
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "C2004-DATA-0001"
    assert body["correlation_id"] == "cor-scenario-missing"
    assert body["component"] == "scenario-registry"
    assert body["stage"] == "scenario.lookup"
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "api_scenario_not_found"
    )
    assert "hunter2" not in response.text


def test_register_dsl_rejects_non_array_scenarios_with_typed_data_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scenarios, "_load_dsl_parser", lambda: lambda _dsl, _sid: None)

    response = client.post(
        "/api/v1/scenarios/register-dsl",
        json={"scenarios": "password=hunter2"},
        headers={"X-Correlation-ID": "cor-scenario-payload"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "C2004-DATA-0002"
    assert body["correlation_id"] == "cor-scenario-payload"
    assert body["component"] == "scenario-registry"
    assert body["stage"] == "payload.validate"
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "api_scenario_payload_invalid"
    )
    assert body["metadata"]["context"]["field"] == "scenarios"
    assert "hunter2" not in response.text


def test_register_dsl_sanitizes_parser_dependency_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _unavailable_parser():
        raise ImportError("password=hunter2 parser import failed")

    monkeypatch.setattr(scenarios, "_load_dsl_parser", _unavailable_parser)

    response = client.post(
        "/api/v1/scenarios/register-dsl",
        json={"id": "demo", "dsl": "GOAL: demo"},
        headers={"X-Correlation-ID": "cor-scenario-parser"},
    )

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "C2004-NET-0002"
    assert body["correlation_id"] == "cor-scenario-parser"
    assert body["component"] == "scenario-parser"
    assert body["stage"] == "dependency.load"
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "api_scenario_parser_unavailable"
    )
    assert "hunter2" not in response.text
    assert "import failed" not in response.text


def test_register_dsl_does_not_mask_parser_programming_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _broken_parser_loader():
        raise AttributeError("password=hunter2 programming defect")

    monkeypatch.setattr(scenarios, "_load_dsl_parser", _broken_parser_loader)

    response = client.post(
        "/api/v1/scenarios/register-dsl",
        json={"id": "demo", "dsl": "GOAL: demo"},
        headers={"X-Correlation-ID": "cor-scenario-defect"},
    )

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "C2004-SYS-0000"
    assert body["correlation_id"] == "cor-scenario-defect"
    assert body["metadata"]["diagnostics"]["exception_type"] == "AttributeError"
    assert "hunter2" not in response.text
    assert "programming defect" not in response.text
