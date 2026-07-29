"""Safe problem-details contracts for the execution API."""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from oqlos.api import execution
from oqlos.errors.fastapi_integration import install_oqlos_error_handler


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    state_manager = SimpleNamespace(scenarios={}, executions={})
    orchestrator = SimpleNamespace(current_execution=None)
    monkeypatch.setattr(execution._ctrl, "state_manager", state_manager)
    monkeypatch.setattr(execution._ctrl, "orchestrator", orchestrator)
    app = FastAPI()
    install_oqlos_error_handler(app)
    app.include_router(execution.router)
    return TestClient(app, raise_server_exceptions=False)


def _assert_problem(
    response,
    *,
    status: int,
    code: str,
    issue_code: str | None,
    stage: str,
) -> dict:
    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == code
    assert body["correlation_id"] == "cor-execution-api"
    assert body["stage"] == stage
    if issue_code is not None:
        assert body["metadata"]["diagnostics"]["issue_code"] == issue_code
    assert "hunter2" not in response.text
    return body


def _headers() -> dict[str, str]:
    return {"X-Correlation-ID": "cor-execution-api"}


def test_start_missing_scenario_is_safe_not_found(client: TestClient) -> None:
    response = client.post(
        "/api/v1/execution/start",
        json={"scenarioId": "password=hunter2"},
        headers=_headers(),
    )

    _assert_problem(
        response,
        status=404,
        code="C2004-DATA-0001",
        issue_code="api_scenario_not_found",
        stage="scenario.lookup",
    )


def test_start_invalid_inline_dsl_is_safe_data_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _invalid_dsl(_scenario_id: str, _dsl: str) -> None:
        raise ValueError("password=hunter2 invalid line")

    monkeypatch.setattr(execution, "_register_dsl_scenario", _invalid_dsl)

    response = client.post(
        "/api/v1/execution/start",
        json={
            "scenarioId": "runtime",
            "content": {"dsl": "password=hunter2"},
        },
        headers=_headers(),
    )

    body = _assert_problem(
        response,
        status=422,
        code="C2004-DATA-0002",
        issue_code="api_execution_request_invalid",
        stage="dsl.validate",
    )
    assert body["metadata"]["context"]["reason"] == "dsl_invalid"


def test_start_unexpected_orchestrator_failure_is_sanitized_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    execution._ctrl.state_manager.scenarios["demo"] = object()

    async def _fail(**_kwargs):
        raise RuntimeError("password=hunter2 internal failure")

    monkeypatch.setattr(
        execution._ctrl.orchestrator,
        "execute_scenario",
        _fail,
        raising=False,
    )

    response = client.post(
        "/api/v1/execution/start",
        json={"scenarioId": "demo"},
        headers=_headers(),
    )

    _assert_problem(
        response,
        status=500,
        code="C2004-SYS-0000",
        issue_code=None,
        stage="api.error",
    )


def test_step_requires_scenario_and_step(client: TestClient) -> None:
    response = client.post(
        "/api/v1/execution/step",
        json={"scenarioId": "password=hunter2"},
        headers=_headers(),
    )

    body = _assert_problem(
        response,
        status=422,
        code="C2004-DATA-0002",
        issue_code="api_execution_request_invalid",
        stage="step.validate",
    )
    assert body["metadata"]["context"]["reason"] == "step_fields_required"


def test_step_missing_scenario_is_safe_not_found(client: TestClient) -> None:
    response = client.post(
        "/api/v1/execution/step",
        json={
            "scenarioId": "password=hunter2",
            "step": {"action": "NOP"},
        },
        headers=_headers(),
    )

    _assert_problem(
        response,
        status=404,
        code="C2004-DATA-0001",
        issue_code="api_scenario_not_found",
        stage="scenario.lookup",
    )


@pytest.mark.parametrize(
    ("method", "path", "operation_id"),
    [
        (
            "POST",
            "/api/v1/execution/password=hunter2/pause",
            "execution.control-by-id",
        ),
        (
            "GET",
            "/api/v1/execution/by-id/password=hunter2",
            "execution.get",
        ),
    ],
)
def test_missing_execution_id_is_safe_not_found(
    client: TestClient, method: str, path: str, operation_id: str
) -> None:
    response = client.request(method, path, headers=_headers())

    body = _assert_problem(
        response,
        status=404,
        code="C2004-DATA-0001",
        issue_code="api_execution_not_found",
        stage="execution.lookup",
    )
    assert body["metadata"]["context"]["operation_id"] == operation_id


def test_legacy_control_without_current_execution_is_conflict(
    client: TestClient,
) -> None:
    response = client.post("/api/v1/execution/pause", headers=_headers())

    _assert_problem(
        response,
        status=409,
        code="C2004-DATA-0003",
        issue_code="api_execution_state_conflict",
        stage="state.validate",
    )
