"""Problem-details contracts for unavailable execution dependencies."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from oqlos.api import execution, state
from oqlos.api.utils import execution_ctrl
from oqlos.errors import OqlosError
from oqlos.errors.fastapi_integration import install_oqlos_error_handler


def _client_for(router) -> TestClient:
    app = FastAPI()
    install_oqlos_error_handler(app)
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _assert_runtime_unavailable(response, *, dependency: str) -> None:
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "C2004-NET-0002"
    assert body["correlation_id"] == "cor-execution-runtime"
    assert body["component"] == "scenario-execution"
    assert body["stage"] == "dependency.resolve"
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "api_execution_runtime_unavailable"
    )
    assert body["metadata"]["context"] == {
        "architecture": "SOA",
        "layer": "oqlos",
        "component": "scenario-execution",
        "stage": "dependency.resolve",
        "problem_source": "runtime-state",
        "operation_id": "execution.dependencies.resolve",
        "upstream_target": "runtime://scenario-execution",
        "dependency": dependency,
    }
    assert "hunter2" not in response.text
    assert "set_dependencies" not in response.text


@pytest.mark.parametrize(
    ("getter_name", "dependency"),
    [
        ("get_state_manager", "state_manager"),
        ("get_orchestrator", "orchestrator"),
    ],
)
def test_dependency_getter_raises_typed_error(
    monkeypatch: pytest.MonkeyPatch,
    getter_name: str,
    dependency: str,
) -> None:
    monkeypatch.setattr(execution_ctrl, dependency, None)

    with pytest.raises(OqlosError) as caught:
        getattr(execution_ctrl, getter_name)()

    assert caught.value.issue_code == "api_execution_runtime_unavailable"
    assert caught.value.public_code == "C2004-NET-0002"
    assert caught.value.status_code == 503
    assert caught.value.detail["dependency"] == dependency


def test_control_by_id_reports_missing_state_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(execution_ctrl, "state_manager", None)

    response = _client_for(execution.router).post(
        "/api/v1/execution/execution-password-hunter2/pause",
        headers={"X-Correlation-ID": "cor-execution-runtime"},
    )

    _assert_runtime_unavailable(response, dependency="state_manager")


def test_control_by_id_reports_missing_orchestrator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        execution_ctrl,
        "state_manager",
        SimpleNamespace(executions={"exec-1": object()}),
    )
    monkeypatch.setattr(execution_ctrl, "orchestrator", None)

    response = _client_for(execution.router).post(
        "/api/v1/execution/exec-1/pause",
        headers={"X-Correlation-ID": "cor-execution-runtime"},
    )

    _assert_runtime_unavailable(response, dependency="orchestrator")


def test_command_control_reports_missing_orchestrator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(execution_ctrl, "orchestrator", None)

    response = _client_for(state.router).post(
        "/api/v1/commands",
        json={"command": "PauseExecution", "data": {}},
        headers={"X-Correlation-ID": "cor-execution-runtime"},
    )

    _assert_runtime_unavailable(response, dependency="orchestrator")
