from __future__ import annotations

import base64
import json

import pytest

from oqlos.hardware.plugins import _maskauth_capability
from oqlos.hardware.plugins._m5_core_http import CoreS3HttpClient
from oqlos.hardware.plugins._maskauth_capability import MaskAuthCapabilityClient


class _Response:
    status = 200

    def read(self) -> bytes:
        return b'{"token":"short-lived-token","expires_in":30}'


class _Connection:
    instances: list["_Connection"] = []

    def __init__(self, host: str, port: int | None, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.request_data: tuple[str, str, bytes, dict[str, str]] | None = None
        self.closed = False
        self.__class__.instances.append(self)

    def request(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: dict[str, str],
    ) -> None:
        self.request_data = (method, path, body, headers)

    def getresponse(self) -> _Response:
        return _Response()

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _fake_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    _Connection.instances.clear()
    monkeypatch.setattr(_maskauth_capability, "HTTPConnection", _Connection)


def test_capability_request_uses_basic_identity_and_exact_scope() -> None:
    client = MaskAuthCapabilityClient(
        "http://maskauth.local:8280/prefix",
        "boardnet",
        "private-secret",
    )

    token = client.token("hardware.node.output.set", "hardware-node:stacknet/output/8")

    assert token == "short-lived-token"
    connection = _Connection.instances[-1]
    assert connection.closed is True
    assert connection.request_data is not None
    method, path, body, headers = connection.request_data
    assert method == "POST"
    assert path == "/prefix/v1/service-capability-tokens"
    expected_basic = base64.b64encode(b"boardnet:private-secret").decode()
    assert headers["Authorization"] == f"Basic {expected_basic}"
    assert json.loads(body) == {
        "application": "boardnet",
        "capability": "hardware.node.output.set",
        "resource": "hardware-node:stacknet/output/8",
        "audience": "stacknet",
        "context": {},
    }


def test_capability_token_is_cached_per_scope() -> None:
    client = MaskAuthCapabilityClient(
        "http://maskauth.local:8280", "boardnet", "private-secret"
    )

    assert client.token("capability", "resource") == "short-lived-token"
    assert client.token("capability", "resource") == "short-lived-token"

    assert len(_Connection.instances) == 1


def test_stacknet_scope_is_exact_for_coil_and_safety_operations() -> None:
    assert CoreS3HttpClient._authorization_scope("lease_acquire", {}) == (
        "hardware.node.output.set",
        "hardware-node:stacknet/output/lease",
    )
    assert CoreS3HttpClient._authorization_scope("set_coil", {"coil": 7}) == (
        "hardware.node.output.set",
        "hardware-node:stacknet/output/8",
    )
    assert CoreS3HttpClient._authorization_scope("all_outputs_off", {}) == (
        "hardware.node.outputs.all-off",
        "hardware-node:stacknet/outputs",
    )


def test_stacknet_mutation_has_bearer_trace_and_idempotency_headers() -> None:
    class _Capabilities:
        def token(self, capability: str, resource: str) -> str:
            assert capability == "hardware.node.output.set"
            assert resource == "hardware-node:stacknet/output/3"
            return "capability-token"

    class _CoreResponse:
        status = 200

        def read(self) -> bytes:
            return b'{"success":true}'

    class _CoreConnection:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}
            self.closed = False

        def request(
            self,
            method: str,
            path: str,
            body: bytes | None = None,
            headers: dict[str, str] | None = None,
        ) -> None:
            assert method == "POST"
            assert path == "/api/v1/oql"
            self.headers = headers or {}

        def getresponse(self) -> _CoreResponse:
            return _CoreResponse()

        def close(self) -> None:
            self.closed = True

    client = CoreS3HttpClient(
        "http://stacknet.local:8080",
        capability_client=_Capabilities(),  # type: ignore[arg-type]
    )
    connection = _CoreConnection()
    client._connection = connection  # type: ignore[assignment]

    assert client.execute("set_coil", {"coil": 2, "value": True})["success"] is True

    assert connection.headers["Authorization"] == "Bearer capability-token"
    assert connection.headers["X-Correlation-ID"].startswith("boardnet-")
    assert connection.headers["Idempotency-Key"]
    assert connection.closed is True
