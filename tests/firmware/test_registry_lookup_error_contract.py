"""Safe problem-details contracts for plugin and peripheral lookup failures."""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from oqlos.api import peripherals, plugins
from oqlos.errors.fastapi_integration import install_oqlos_error_handler


def _client() -> TestClient:
    app = FastAPI()
    install_oqlos_error_handler(app)
    app.include_router(plugins.router)
    app.include_router(peripherals.router)
    return TestClient(app, raise_server_exceptions=False)


def test_missing_plugin_returns_safe_typed_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(plugins.PluginRegistry, "get_plugin_class", lambda _id: None)

    response = _client().get(
        "/api/v1/plugins/password=hunter2",
        headers={"X-Correlation-ID": "cor-plugin-missing"},
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "C2004-DATA-0001"
    assert body["correlation_id"] == "cor-plugin-missing"
    assert body["component"] == "plugin-registry"
    assert body["stage"] == "plugin.lookup"
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "api_plugin_not_found"
    )
    assert "hunter2" not in response.text


@pytest.mark.parametrize(
    ("method", "path", "payload", "operation_id"),
    [
        (
            "GET",
            "/api/v1/peripherals/password=hunter2",
            None,
            "peripheral.get",
        ),
        (
            "PUT",
            "/api/v1/peripherals/password=hunter2",
            {"currentValue": 1},
            "peripheral.update",
        ),
        (
            "POST",
            "/api/v1/peripherals/password=hunter2/set?value=1",
            None,
            "peripheral.set",
        ),
    ],
)
def test_missing_peripheral_returns_safe_typed_not_found(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    payload,
    operation_id: str,
) -> None:
    monkeypatch.setattr(
        peripherals._ctrl,
        "state_manager",
        SimpleNamespace(peripherals={}),
    )

    response = _client().request(
        method,
        path,
        json=payload,
        headers={"X-Correlation-ID": "cor-peripheral-missing"},
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "C2004-DATA-0001"
    assert body["correlation_id"] == "cor-peripheral-missing"
    assert body["component"] == "peripheral-registry"
    assert body["stage"] == "peripheral.lookup"
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "api_peripheral_not_found"
    )
    assert body["metadata"]["context"]["operation_id"] == operation_id
    assert "hunter2" not in response.text
