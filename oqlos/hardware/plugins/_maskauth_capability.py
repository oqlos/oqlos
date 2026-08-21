"""Short-lived MaskAuth capability token client for hardware service identities."""

from __future__ import annotations

import base64
import json
from http.client import HTTPConnection, HTTPSConnection
from threading import Lock
from time import monotonic
from typing import Any
from urllib.parse import urlsplit


class MaskAuthCapabilityClient:
    """Mint and cache narrowly scoped tokens for StackNet commands."""

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        application: str = "boardnet",
        audience: str = "stacknet",
        timeout: float = 2.0,
    ) -> None:
        parsed = urlsplit(base_url.rstrip("/"))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"Invalid MaskAuth base_url: {base_url}")
        if not client_id or not client_secret:
            raise ValueError("MaskAuth client_id and client_secret are required")
        self._scheme = parsed.scheme
        self._host = parsed.hostname
        self._port = parsed.port
        self._base_path = parsed.path.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.application = application
        self.audience = audience
        self.timeout = timeout
        self._cache: dict[tuple[str, str], tuple[str, float]] = {}
        self._lock = Lock()

    def token(self, capability: str, resource: str) -> str:
        """Return a cached token while it has at least five seconds of life."""
        key = (capability, resource)
        with self._lock:
            cached = self._cache.get(key)
            if cached and cached[1] > monotonic() + 5:
                return cached[0]
            token, expires_in = self._request_token(capability, resource)
            self._cache[key] = (token, monotonic() + expires_in)
            return token

    def _request_token(self, capability: str, resource: str) -> tuple[str, int]:
        connection_type = HTTPSConnection if self._scheme == "https" else HTTPConnection
        connection = connection_type(self._host, self._port, timeout=self.timeout)
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode("ascii")
        body = json.dumps(
            {
                "application": self.application,
                "capability": capability,
                "resource": resource,
                "audience": self.audience,
                "context": {},
            },
            separators=(",", ":"),
        ).encode()
        try:
            connection.request(
                "POST",
                f"{self._base_path}/v1/service-capability-tokens",
                body=body,
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            response = connection.getresponse()
            raw = response.read()
            status = response.status
        finally:
            connection.close()
        if status >= 400:
            raise RuntimeError(
                f"MaskAuth capability request failed: HTTP {status}: "
                f"{raw.decode(errors='replace')}"
            )
        try:
            payload: Any = json.loads(raw.decode())
            token = str(payload.get("token", "")) if isinstance(payload, dict) else ""
            expires_in = int(payload.get("expires_in", 0)) if isinstance(payload, dict) else 0
        except (UnicodeDecodeError, ValueError, TypeError) as exc:
            raise RuntimeError(f"MaskAuth returned an invalid token response: {exc}") from exc
        if not token or expires_in <= 0:
            raise RuntimeError("MaskAuth returned an invalid capability token response")
        return token, expires_in
