"""Regression: OqlosError serializes to the standard OqlIssue body and the
FastAPI handler returns it with the requested status code.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from oqlos.errors import OqlosError
from oqlos.errors.catalog import get_issue_definition
from oqlos.errors.fastapi_integration import install_oqlos_error_handler


def test_oqlos_error_uses_catalog_defaults_for_known_code():
    err = OqlosError("modbus_adc_disabled_but_present", status_code=409)
    issue = err.to_issue()

    assert issue["code"] == "modbus_adc_disabled_but_present"
    assert issue["domain"] == "config"
    assert issue["severity"] == "warning"
    assert "modbus-adc" in issue["message"]
    assert issue["repair"]["id"] == "enable_modbus_adc_config"
    assert issue["repair"]["actuation_risk"] == "config"


def test_oqlos_error_overrides_and_detail():
    err = OqlosError(
        "modbus_config_mismatch",
        message="Custom message",
        detail={"serial_port": "/dev/ttyUSB1"},
        severity="critical",
    )
    issue = err.to_issue()

    assert issue["message"] == "Custom message"
    assert issue["severity"] == "critical"
    assert issue["detail"] == {"serial_port": "/dev/ttyUSB1"}


def test_oqlos_error_tolerates_unknown_code():
    err = OqlosError("some_brand_new_code_not_yet_cataloged")
    issue = err.to_issue()

    assert issue["code"] == "some_brand_new_code_not_yet_cataloged"
    assert issue["domain"] == "unknown"
    assert issue["severity"] == "error"
    assert "repair" not in issue


def test_oqlos_error_accepts_valid_public_code_and_correlation_override():
    err = OqlosError(
        "remote_oql_execution_failed",
        public_code="C2004-NET-0003",
        correlation_id="cor-upstream",
    )

    assert err.public_code == "C2004-NET-0003"
    assert err.correlation_id == "cor-upstream"


def test_oqlos_error_rejects_unknown_public_code_override():
    err = OqlosError(
        "remote_oql_execution_failed",
        public_code="C2004-NET-9999",
    )

    assert err.public_code == "C2004-HW-0012"


def test_oqlos_error_fastapi_handler_returns_standard_body():
    app = FastAPI()
    install_oqlos_error_handler(app)

    @app.get("/boom")
    async def boom():
        raise OqlosError("serial_port_busy", status_code=409, detail={"port": "/dev/ttyUSB0"})

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")

    assert resp.status_code == 409
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["code"] == "C2004-HW-0013"
    assert body["error_code"] == "C2004-HW-0013"
    assert body["domain"] == "hardware"
    assert body["status"] == 409
    assert body["ok"] is False
    assert body["metadata"]["context"] == {"port": "/dev/ttyUSB0"}
    diagnostics = body["metadata"]["diagnostics"]
    assert diagnostics["issue_code"] == "serial_port_busy"
    assert diagnostics["repair"]["id"] == "release_serial_port"
    assert body["correlation_id"] == resp.headers["x-correlation-id"]
    assert body["architecture"] == "SOA"
    assert body["layer"] == "oqlos"
    assert body["component"] == "oqlos-api"
    assert body["stage"] == "api.error"


def test_oqlos_error_handler_can_be_installed_on_router_only_test_app():
    app = FastAPI()
    install_oqlos_error_handler(app)

    @app.get("/disabled")
    async def disabled():
        raise OqlosError("api_oql_transport_disabled", status_code=503)

    resp = TestClient(app, raise_server_exceptions=False).get("/disabled")

    assert resp.status_code == 503
    body = resp.json()
    assert body["code"] == "C2004-HW-0012"
    assert body["domain"] == "hardware"
    diagnostics = body["metadata"]["diagnostics"]
    assert diagnostics["issue_code"] == "api_oql_transport_disabled"
    assert diagnostics["repair"]["id"] == "enable_oql_mqtt_transport"


def test_catalog_lookup_still_available_for_known_code():
    definition = get_issue_definition("firmware_not_real")
    assert definition is not None
    assert definition.repair.actuation_risk == "physical"


def test_http_exception_is_wrapped_as_c2004_problem_details():
    app = FastAPI()
    install_oqlos_error_handler(app)

    @app.get("/missing")
    async def missing():
        raise HTTPException(status_code=404, detail="Peripheral not found")

    resp = TestClient(app, raise_server_exceptions=False).get(
        "/missing", headers={"X-Correlation-ID": "cor-test-boundary"}
    )

    assert resp.status_code == 404
    assert resp.json()["code"] == "C2004-DATA-0001"
    assert resp.json()["correlation_id"] == "cor-test-boundary"
    assert resp.headers["x-correlation-id"] == "cor-test-boundary"


def test_http_400_uses_invalid_request_code_with_matching_catalog_status():
    app = FastAPI()
    install_oqlos_error_handler(app)

    @app.get("/invalid")
    async def invalid():
        raise HTTPException(status_code=400, detail="Invalid command syntax")

    resp = TestClient(app, raise_server_exceptions=False).get("/invalid")

    assert resp.status_code == 400
    assert resp.json()["status"] == 400
    assert resp.json()["code"] == "C2004-DATA-0004"


def test_upstream_problem_code_is_validated_normalized_and_sanitized():
    app = FastAPI()
    install_oqlos_error_handler(app)

    @app.get("/upstream")
    async def upstream():
        raise HTTPException(
            status_code=503,
            detail={
                "path": "/api/v1/hardware/health",
                "response": {
                    "code": "C2004-NET-0003",
                    "status": 200,
                    "detail": "password=hunter2",
                    "correlation_id": "cor-upstream-safe",
                    "architecture": "SOA",
                    "layer": "firmware",
                    "component": "hardware-agent",
                    "stage": "health.timeout",
                    "metadata": {
                        "context": {"operation_id": "hardware.health"},
                        "secret": "must-not-pass",
                    },
                },
            },
        )

    resp = TestClient(app, raise_server_exceptions=False).get("/upstream")

    assert resp.status_code == 504
    body = resp.json()
    assert body["code"] == "C2004-NET-0003"
    assert body["status"] == 504
    assert body["correlation_id"] == "cor-upstream-safe"
    assert body["component"] == "hardware-agent"
    assert body["metadata"]["context"]["operation_id"] == "hardware.health"
    assert body["metadata"]["context"]["upstream_target"] == (
        "oqlos-api://configured-target/api/v1/hardware/health"
    )
    assert "hunter2" not in resp.text
    assert "must-not-pass" not in resp.text


def test_unknown_upstream_code_falls_back_to_http_status_mapping():
    app = FastAPI()
    install_oqlos_error_handler(app)

    @app.get("/upstream-invalid-code")
    async def upstream_invalid_code():
        raise HTTPException(
            status_code=503,
            detail={
                "response": {
                    "code": "C2004-HW-9999",
                    "detail": "private upstream failure",
                }
            },
        )

    resp = TestClient(app, raise_server_exceptions=False).get(
        "/upstream-invalid-code"
    )

    assert resp.status_code == 503
    assert resp.json()["code"] == "C2004-NET-0002"
    assert "private upstream failure" not in resp.text


def test_invalid_correlation_header_is_replaced():
    app = FastAPI()
    install_oqlos_error_handler(app)

    @app.get("/invalid-correlation")
    async def invalid_correlation():
        raise HTTPException(status_code=404, detail="missing")

    resp = TestClient(app, raise_server_exceptions=False).get(
        "/invalid-correlation",
        headers={"X-Correlation-ID": "invalid correlation with spaces"},
    )

    assert resp.status_code == 404
    assert resp.json()["correlation_id"].startswith("cor-")
    assert resp.headers["x-correlation-id"] == resp.json()["correlation_id"]


def test_request_validation_is_wrapped_as_data_0002():
    app = FastAPI()
    install_oqlos_error_handler(app)

    @app.get("/validated")
    async def validated(required_count: int):
        return {"required_count": required_count}

    resp = TestClient(app, raise_server_exceptions=False).get("/validated")

    assert resp.status_code == 422
    assert resp.json()["code"] == "C2004-DATA-0002"
    assert resp.json()["metadata"]["context"]["errors"]


def test_uncoded_exception_uses_sys_0000_without_leaking_message():
    app = FastAPI()
    install_oqlos_error_handler(app)

    @app.get("/uncoded")
    async def uncoded():
        raise RuntimeError("internal secret detail")

    resp = TestClient(app, raise_server_exceptions=False).get("/uncoded")

    assert resp.status_code == 500
    assert resp.json()["code"] == "C2004-SYS-0000"
    assert "internal secret detail" not in resp.text
    assert resp.json()["metadata"]["diagnostics"]["exception_type"] == "RuntimeError"


def test_untyped_http_500_uses_catalog_message_without_leaking_detail():
    app = FastAPI()
    install_oqlos_error_handler(app)

    @app.get("/raw-http-500")
    async def raw_http_500():
        raise HTTPException(
            status_code=500,
            detail={
                "error": "password=hunter2",
                "internal_path": "/private/config",
            },
        )

    resp = TestClient(app, raise_server_exceptions=False).get(
        "/raw-http-500",
        headers={"X-Correlation-ID": "cor-http-500"},
    )

    assert resp.status_code == 500
    body = resp.json()
    assert body["code"] == "C2004-SYS-0000"
    assert body["correlation_id"] == "cor-http-500"
    assert body["stage"] == "http.exception"
    assert body["metadata"]["context"]["problem_source"] == "api-boundary"
    assert "hunter2" not in resp.text
    assert "/private/config" not in resp.text
