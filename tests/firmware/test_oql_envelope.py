"""Envelope (de)serialization for the OQL-over-MQTT transport."""

from __future__ import annotations

import json

import pytest

from oqlos.errors import OqlosError
from oqlos.errors.c2004_catalog_generated import CATALOG
from oqlos.hardware.transport import OqlRequest, OqlResponse, build_topics
from oqlos.hardware.transport.mqtt_protocol import (
    MqttEnvelopeError,
    mqtt_error_response,
)
from oqlos.tools.cql_cli.commands import run_single_command
from oqlos.tools.cql_cli.utils import build_result_payload


def test_request_json_roundtrip():
    req = OqlRequest(
        correlation_id="c1",
        oql="SET 'VALVE-NC' 'open'",
        reply_to="oqlos/c2004/pi-hw/oql/response/c1",
        kind="command",
        sensors={"AI01": 7.5},
        skip_waits=True,
        timeout_ms=5000,
        source="test",
    )
    back = OqlRequest.from_json(req.to_json())
    assert back.correlation_id == "c1"
    assert back.oql == "SET 'VALVE-NC' 'open'"
    assert back.sensors == {"AI01": 7.5}
    assert back.timeout_ms == 5000
    assert json.loads(req.to_json())["v"] == 1


def test_request_defaults_do_not_skip_waits():
    req = OqlRequest(
        correlation_id="c1",
        oql="SET WAIT '1 s'",
    )
    back = OqlRequest.from_json(
        json.dumps({"correlation_id": "c1", "oql": "SET WAIT '1 s'"})
    )

    assert req.skip_waits is False
    assert back.skip_waits is False


def test_response_json_roundtrip():
    resp = OqlResponse(
        "c1", ok=True, result={"ok": True, "passed": 1}, error=None, node_id="pi-hw"
    )
    back = OqlResponse.from_json(resp.to_json())
    assert back.correlation_id == "c1"
    assert back.ok is True
    assert back.result == {"ok": True, "passed": 1}
    assert back.node_id == "pi-hw"


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (TimeoutError("late"), "C2004-NET-0003"),
        (ValueError("invalid field"), "C2004-DATA-0002"),
        (OSError("device unavailable"), "C2004-HW-0012"),
        (RuntimeError("serial port unavailable"), "C2004-HW-0012"),
        (RuntimeError("unexpected internal failure"), "C2004-SYS-0000"),
        (OqlosError("serial_port_busy", status_code=409), "C2004-HW-0013"),
    ],
)
def test_mqtt_error_response_detects_canonical_error_code(error, expected_code):
    response = mqtt_error_response(
        "cor-error-matrix",
        error,
        node_id="pi-hw",
        stage="mqtt.execute",
    )

    assert response.ok is False
    assert response.error_code == expected_code
    assert response.correlation_id == "cor-error-matrix"
    assert response.node_id == "pi-hw"
    assert response.stage == "mqtt.execute"
    assert response.error == CATALOG[expected_code].message
    assert str(error) not in response.error


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        b"[]",
        b'{"v": 999, "correlation_id": "c1"}',
        b'{"v": 1, "timeout_ms": []}',
    ],
)
def test_request_rejects_malformed_or_unsupported_envelopes(payload):
    with pytest.raises(MqttEnvelopeError):
        OqlRequest.from_json(payload)


def test_response_rejects_missing_correlation_id():
    with pytest.raises(MqttEnvelopeError):
        OqlResponse.from_json(b'{"v": 1, "ok": false}')


def test_topics_layout():
    t = build_topics("oqlos/c2004", "pi-hw")
    assert t.request == "oqlos/c2004/pi-hw/oql/request"
    assert t.response_for("abc") == "oqlos/c2004/pi-hw/oql/response/abc"
    assert t.response_wildcard == "oqlos/c2004/pi-hw/oql/response/+"
    assert t.events == "oqlos/c2004/pi-hw/oql/events"
    assert t.status == "oqlos/c2004/pi-hw/oql/status"


def test_build_result_payload_is_json_serializable():
    result = run_single_command(
        "SET 'VALVE-NC' 'open'",
        mode="dry-run",
        quiet=True,
        sensors={},
        firmware_url="http://localhost:8202",
        skip_waits=True,
    )
    payload = build_result_payload(result)
    # Must survive a JSON round-trip (it crosses the MQTT wire).
    assert json.loads(json.dumps(payload))["ok"] is True
