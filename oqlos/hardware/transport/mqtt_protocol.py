"""Versioned envelopes and topic naming for the OQL-over-MQTT transport."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from oqlos.errors import OqlosError
from oqlos.errors.c2004_catalog_generated import CATALOG

ENVELOPE_VERSION = 1


class MqttEnvelopeError(ValueError):
    """Raised when an MQTT request/response envelope cannot be decoded safely."""


def _decode_envelope(raw: str | bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        raise MqttEnvelopeError("invalid JSON envelope") from exc
    if not isinstance(data, dict):
        raise MqttEnvelopeError("MQTT envelope must be a JSON object")
    version = data.get("v", ENVELOPE_VERSION)
    if version != ENVELOPE_VERSION:
        raise MqttEnvelopeError("unsupported MQTT envelope version")
    return data


@dataclass(frozen=True)
class Topics:
    """Resolved MQTT topic strings for one hardware node."""

    prefix: str
    node_id: str

    @property
    def request(self) -> str:
        return f"{self.prefix}/{self.node_id}/oql/request"

    @property
    def response_base(self) -> str:
        return f"{self.prefix}/{self.node_id}/oql/response"

    @property
    def response_wildcard(self) -> str:
        return f"{self.response_base}/+"

    @property
    def events(self) -> str:
        return f"{self.prefix}/{self.node_id}/oql/events"

    @property
    def status(self) -> str:
        return f"{self.prefix}/{self.node_id}/oql/status"

    def response_for(self, correlation_id: str) -> str:
        return f"{self.response_base}/{correlation_id}"


def build_topics(prefix: str, node_id: str) -> Topics:
    return Topics(prefix=prefix.rstrip("/"), node_id=node_id)


class _JsonEnvelopeMixin:
    """Shared serialization for versioned MQTT envelope dataclasses."""

    def to_json(self) -> str:
        payload = asdict(self)
        payload["v"] = ENVELOPE_VERSION
        return json.dumps(payload, ensure_ascii=False)


@dataclass
class OqlRequest(_JsonEnvelopeMixin):
    """A request to execute on a remote hardware node."""

    correlation_id: str
    oql: str
    reply_to: str = ""
    kind: str = "command"  # "command" | "script" | "manage" | "ping"
    mode: str = "execute"
    sensors: dict[str, float] | None = None
    args: dict[str, Any] | None = None
    skip_waits: bool = False
    timeout_ms: int = 15000
    source: str = ""

    @classmethod
    def from_json(cls, raw: str | bytes) -> "OqlRequest":
        data = _decode_envelope(raw)
        try:
            return cls(
                correlation_id=str(data["correlation_id"]),
                oql=str(data.get("oql", "")),
                reply_to=str(data.get("reply_to", "")),
                kind=str(data.get("kind", "command")),
                mode=str(data.get("mode", "execute")),
                sensors=data.get("sensors") or None,
                args=data.get("args") or None,
                skip_waits=bool(data.get("skip_waits", False)),
                timeout_ms=int(data.get("timeout_ms", 15000)),
                source=str(data.get("source", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise MqttEnvelopeError("invalid MQTT request envelope") from exc


@dataclass
class OqlResponse(_JsonEnvelopeMixin):
    """The result of executing OQL on a remote hardware node."""

    correlation_id: str
    ok: bool
    result: dict[str, Any] | None = None
    error: str | None = None
    node_id: str = ""
    error_code: str | None = None
    architecture: str = "SOA"
    layer: str = "firmware"
    component: str = "oql-mqtt-agent"
    stage: str | None = None

    @classmethod
    def from_json(cls, raw: str | bytes) -> "OqlResponse":
        data = _decode_envelope(raw)
        try:
            return cls(
                correlation_id=str(data["correlation_id"]),
                ok=bool(data.get("ok", False)),
                result=data.get("result"),
                error=data.get("error"),
                node_id=str(data.get("node_id", "")),
                error_code=data.get("error_code"),
                architecture=str(data.get("architecture", "SOA")),
                layer=str(data.get("layer", "firmware")),
                component=str(data.get("component", "oql-mqtt-agent")),
                stage=data.get("stage"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise MqttEnvelopeError("invalid MQTT response envelope") from exc


def mqtt_error_response(
    correlation_id: str,
    exc: Exception,
    *,
    node_id: str,
    stage: str,
) -> OqlResponse:
    """Map an agent failure to the same C2004 envelope as the HTTP boundary."""
    if isinstance(exc, OqlosError):
        code = exc.public_code
    elif isinstance(exc, TimeoutError):
        code = "C2004-NET-0003"
    elif isinstance(exc, ValueError):
        code = "C2004-DATA-0002"
    elif isinstance(exc, OSError) or "serial port" in str(exc).lower():
        code = "C2004-HW-0012"
    else:
        code = "C2004-SYS-0000"
    entry = CATALOG.get(code) or CATALOG["C2004-SYS-0000"]
    return OqlResponse(
        correlation_id,
        ok=False,
        result=None,
        error=entry.message,
        node_id=node_id,
        error_code=code,
        stage=stage,
    )
