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
