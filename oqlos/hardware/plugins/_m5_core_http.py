"""Synchronous client for the StackNet OQL-over-LAN/Wi-Fi endpoint."""

from __future__ import annotations

import json
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from ._maskauth_capability import MaskAuthCapabilityClient


class CoreS3HttpClient:
    def __init__(self, base_url: str, token: str = "", timeout: float = 2.0,
                 capability_client: MaskAuthCapabilityClient | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.capability_client = capability_client
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"Invalid StackNet base_url: {base_url}")
        self._scheme = parsed.scheme
        self._host = parsed.hostname
        self._port = parsed.port
        self._base_path = parsed.path.rstrip("/")
        self._connection: HTTPConnection | HTTPSConnection | None = None
        self.lease_id = ""
        self.lease_ttl_ms = 3000

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _get_connection(self) -> HTTPConnection | HTTPSConnection:
        if self._connection is None:
            connection_type = HTTPSConnection if self._scheme == "https" else HTTPConnection
            self._connection = connection_type(self._host, self._port, timeout=self.timeout)
        return self._connection

    def _request(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        data = None
        method = "GET"
        if body is not None:
            data = json.dumps(body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
            method = "POST"
        if self.token:
            headers["X-OQL-Token"] = self.token
        if body is not None and self.capability_client is not None:
            command = str(body.get("command", ""))
            params = body.get("params") if isinstance(body.get("params"), dict) else {}
            capability, resource = self._authorization_scope(command, params)
            headers["Authorization"] = f"Bearer {self.capability_client.token(capability, resource)}"
            headers["X-Correlation-ID"] = f"boardnet-{uuid4()}"
            headers["Idempotency-Key"] = str(uuid4())
        request_path = f"{self._base_path}{path}"
        raw = b""
        for attempt in range(2):
            try:
                connection = self._get_connection()
                connection.request(method, request_path, body=data, headers=headers)
                response = connection.getresponse()
                raw = response.read()
                status = response.status
                # ESP-IDF closes request sockets even when it omits an explicit
                # Connection: close header. Reusing that half-closed socket makes
                # the next lease or output request wait until the full timeout.
                self.close()
                if status >= 400:
                    raise RuntimeError(
                        f"StackNet HTTP failed: HTTP {status}: {raw.decode('utf-8', errors='replace')}"
                    )
                break
            except (HTTPException, OSError, TimeoutError) as exc:
                self.close()
                if attempt == 0:
                    continue
                raise RuntimeError(f"StackNet HTTP failed: {exc}") from exc
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise RuntimeError(f"StackNet returned invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("StackNet returned a non-object JSON response")
        return payload

    @staticmethod
    def _authorization_scope(command: str, params: dict[str, Any]) -> tuple[str, str]:
        if command == "all_outputs_off":
            return "hardware.node.outputs.all-off", "hardware-node:stacknet/outputs"
        if command == "replace_outputs":
            return "hardware.node.outputs.replace", "hardware-node:stacknet/outputs"
        if command == "config_apply":
            return "hardware.node.network.identity.configure", "hardware-node:stacknet/network"
        if command == "set_coil" and isinstance(params.get("coil"), int):
            return "hardware.node.output.set", f"hardware-node:stacknet/output/{params['coil'] + 1}"
        return "hardware.node.output.set", "hardware-node:stacknet/output/lease"

    def status(self) -> dict[str, Any]:
        return self._request("/api/v1/oql/status")

    def execute(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        effective_params = dict(params)
        if command in {"set_coil", "replace_outputs", "config_apply"} and self.lease_id:
            effective_params.setdefault("lease_id", self.lease_id)
        return self._request("/api/v1/oql", {"command": command, "params": effective_params})

    def acquire_lease(self, lease_id: str, ttl_ms: int) -> dict[str, Any]:
        payload = self._request(
            "/api/v1/oql",
            {"command": "lease_acquire", "params": {"lease_id": lease_id, "ttl_ms": ttl_ms}},
        )
        self.lease_id = lease_id
        self.lease_ttl_ms = ttl_ms
        return payload

    def renew_lease(self) -> dict[str, Any]:
        return self._request(
            "/api/v1/oql",
            {"command": "lease_renew", "params": {"lease_id": self.lease_id, "ttl_ms": self.lease_ttl_ms}},
        )

    def release_lease(self) -> dict[str, Any]:
        try:
            return self._request(
                "/api/v1/oql",
                {"command": "lease_release", "params": {"lease_id": self.lease_id}},
            )
        finally:
            self.lease_id = ""
