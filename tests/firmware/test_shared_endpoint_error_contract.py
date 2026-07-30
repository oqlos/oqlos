"""Safe problem-details contract for shared OqlOS endpoint helpers."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from oqlos.errors.fastapi_integration import install_oqlos_error_handler
from oqlos.shared._endpoint_helpers import get_or_404


def test_get_or_404_returns_typed_sanitized_problem() -> None:
    app = FastAPI()
    install_oqlos_error_handler(app)

    @app.get("/resource/{resource_id}")
    async def resource(resource_id: str):
        return get_or_404(
            {},
            resource_id,
            f"missing resource {resource_id} password=hunter2",
        )

    response = TestClient(app, raise_server_exceptions=False).get(
        "/resource/private-resource",
        headers={"X-Correlation-ID": "cor-shared-helper"},
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["x-correlation-id"] == "cor-shared-helper"
    body = response.json()
    assert body["code"] == "C2004-DATA-0001"
    assert body["correlation_id"] == "cor-shared-helper"
    assert body["component"] == "endpoint-helper"
    assert body["stage"] == "resource.lookup"
    assert body["metadata"]["context"] == {
        "architecture": "SOA",
        "layer": "oqlos",
        "component": "endpoint-helper",
        "stage": "resource.lookup",
        "problem_source": "request",
        "operation_id": "shared.resource.get",
    }
    assert body["metadata"]["diagnostics"]["issue_code"] == (
        "api_resource_not_found"
    )
    assert "private-resource" not in response.text
    assert "hunter2" not in response.text
