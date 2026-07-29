"""Problem-details contracts for the legacy execution command endpoint."""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from oqlos.api import state
from oqlos.errors.fastapi_integration import install_oqlos_error_handler


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        state._ctrl,
        "state_manager",
        SimpleNamespace(scenarios={}),
    )
    monkeypatch.setattr(
        state._ctrl,
        "orchestrator",
        SimpleNamespace(current_execution=None),
    )
    app = FastAPI()
    install_oqlos_error_handler(app)
    app.include_router(state.router)
    return TestClient(app, raise_server_exceptions=False)


def _post_command(client: TestClient, command: str, data: dict | None = None):
    return client.post(
        "/api/v1/commands",
        json={"command": command, "data": data},
        headers={"X-Correlation-ID": "cor-execution-command"},
    )


def _assert_typed_error(
    response,
    *,
    status: int,
    code: str,
    issue_code: str,
    stage: str,
) -> dict:
    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == code
    assert body["correlation_id"] == "cor-execution-command"
    assert body["component"] == "scenario-execution"
    assert body["stage"] == stage
    assert body["metadata"]["diagnostics"]["issue_code"] == issue_code
    assert "hunter2" not in response.text
    return body


def test_start_requires_scenario_or_inline_dsl(client: TestClient) -> None:
    response = _post_command(client, "StartExecution", {})

    body = _assert_typed_error(
        response,
        status=422,
        code="C2004-DATA-0002",
        issue_code="api_execution_request_invalid",
        stage="source.validate",
    )
    assert body["metadata"]["context"]["reason"] == "source_required"


def test_start_rejects_invalid_dsl_without_reflecting_lines(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        state,
        "_maybe_register_dsl_from_content",
        lambda _data, _scenario_id: (None, ["password=hunter2"]),
    )

    response = _post_command(
        client,
        "StartExecution",
        {"scenarioId": "runtime", "dsl": "password=hunter2"},
    )

    body = _assert_typed_error(
        response,
        status=422,
        code="C2004-DATA-0002",
        issue_code="api_execution_request_invalid",
        stage="dsl.validate",
    )
    assert body["metadata"]["context"]["reason"] == "dsl_invalid"


def test_start_rejects_dsl_without_executable_steps(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        state,
        "_maybe_register_dsl_from_content",
        lambda _data, _scenario_id: (SimpleNamespace(steps=[]), []),
    )

    response = _post_command(
        client,
        "StartExecution",
        {"scenarioId": "runtime", "dsl": "GOAL: password=hunter2"},
    )

    body = _assert_typed_error(
        response,
        status=422,
        code="C2004-DATA-0002",
        issue_code="api_execution_request_invalid",
        stage="dsl.validate",
    )
    assert body["metadata"]["context"]["reason"] == "dsl_empty"


def test_start_missing_scenario_returns_safe_not_found(client: TestClient) -> None:
    response = _post_command(
        client,
        "StartExecution",
        {"scenarioId": "password=hunter2"},
    )

    _assert_typed_error(
        response,
        status=404,
        code="C2004-DATA-0001",
        issue_code="api_scenario_not_found",
        stage="scenario.lookup",
    )


def test_unknown_command_is_not_http_200(client: TestClient) -> None:
    response = _post_command(client, "password=hunter2", {})

    body = _assert_typed_error(
        response,
        status=422,
        code="C2004-DATA-0002",
        issue_code="api_execution_request_invalid",
        stage="command.resolve",
    )
    assert body["metadata"]["context"]["reason"] == "command_unsupported"


def test_control_without_current_execution_is_conflict(client: TestClient) -> None:
    response = _post_command(client, "PauseExecution", {})

    _assert_typed_error(
        response,
        status=409,
        code="C2004-DATA-0003",
        issue_code="api_execution_state_conflict",
        stage="state.validate",
    )
