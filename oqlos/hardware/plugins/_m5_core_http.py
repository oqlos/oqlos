"""Synchronous client for the CoreS3 OQL-over-WiFi endpoint."""

from __future__ import annotations

import json
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from typing import Any
from urllib.parse import urlsplit


class CoreS3HttpClient:
    def __init__(self, base_url: str, token: str = "", timeout: float = 2.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"Invalid CoreS3 base_url: {base_url}")
        self._scheme = parsed.scheme
        self._host = parsed.hostname
        self._port = parsed.port
        self._base_path = parsed.path.rstrip("/")
        self._connection: HTTPConnection | HTTPSConnection | None = None

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
        request_path = f"{self._base_path}{path}"
        raw = b""
        for attempt in range(2):
            try:
                connection = self._get_connection()
                connection.request(method, request_path, body=data, headers=headers)
                response = connection.getresponse()
                raw = response.read()
                status = response.status
                if response.getheader("Connection", "").lower() == "close":
                    self.close()
                if status >= 400:
                    raise RuntimeError(
                        f"CoreS3 HTTP failed: HTTP {status}: {raw.decode('utf-8', errors='replace')}"
                    )
                break
            except (HTTPException, OSError, TimeoutError) as exc:
                self.close()
                if attempt == 0:
                    continue
                raise RuntimeError(f"CoreS3 HTTP failed: {exc}") from exc
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise RuntimeError(f"CoreS3 returned invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("CoreS3 returned a non-object JSON response")
        return payload

    def status(self) -> dict[str, Any]:
        return self._request("/api/v1/oql/status")

    def execute(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        return self._request("/api/v1/oql", {"command": command, "params": params})
