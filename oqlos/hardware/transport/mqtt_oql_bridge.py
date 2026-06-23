"""
oqlos.hardware.transport.mqtt_oql_bridge — OQL command transport over MQTT.

This is the inter-node transport that lets the application node (e.g. pi109)
drive a dedicated hardware Raspberry Pi (e.g. pi110) by sending OQL command/script
text over an MQTT broker. The remote agent parses+executes the OQL against its
local hardware gateway and publishes a correlated response.

Two sides share one envelope:

* :class:`OqlMqttController` — runs on the app node. ``execute(oql)`` publishes a
  request and ``await``\\ s the correlated response (or a synthetic timeout).
* :class:`OqlMqttAgent` — runs on the hardware Pi. Subscribes to requests, runs the
  OQL via the existing CQL interpreter against an injected, already-initialized
  :class:`~oqlos.hardware.plugin_gateway.PluginHardwareGateway`, and replies.

Why a dedicated paho client instead of :class:`oqlos.hardware.drivers.mqtt.MqttDriver`:
that driver only caches "last message per topic" with no request/response
correlation — unusable as an RPC transport. Here every request carries a
``correlation_id`` mapped to an :class:`asyncio.Future`.

Topic scheme (``prefix`` default ``oqlos/c2004``, per-node ``node_id``)::

    <prefix>/<node_id>/oql/request          controller -> agent   QoS 1
    <prefix>/<node_id>/oql/response/<corr>  agent -> controller   QoS 1
    <prefix>/<node_id>/oql/events           agent -> all          QoS 0
    <prefix>/<node_id>/oql/status           agent -> all          QoS 1 retained (last-will)
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import asdict, dataclass
from typing import Any

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

ENVELOPE_VERSION = 1
LOCAL_FIRMWARE_URL = "http://localhost:8202"


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Topics:
    """Resolved topic strings for one node."""

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


# ---------------------------------------------------------------------------
# Envelopes
# ---------------------------------------------------------------------------
@dataclass
class OqlRequest:
    """A request to execute on a remote node.

    For ``kind`` in {"command", "script"} the ``oql`` field carries OQL text.
    For ``kind == "manage"`` the ``oql`` field carries the management verb name
    (see :mod:`oqlos.hardware.transport.manage_ops`) and ``args`` carries its
    parameters. ``kind == "ping"`` is a liveness probe.
    """

    correlation_id: str
    oql: str
    reply_to: str = ""
    kind: str = "command"  # "command" | "script" | "manage" | "ping"
    mode: str = "execute"
    sensors: dict[str, float] | None = None
    args: dict[str, Any] | None = None
    skip_waits: bool = True
    timeout_ms: int = 15000
    source: str = ""

    def to_json(self) -> str:
        payload = asdict(self)
        payload["v"] = ENVELOPE_VERSION
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str | bytes) -> "OqlRequest":
        data = json.loads(raw)
        return cls(
            correlation_id=str(data["correlation_id"]),
            oql=str(data.get("oql", "")),
            reply_to=str(data.get("reply_to", "")),
            kind=str(data.get("kind", "command")),
            mode=str(data.get("mode", "execute")),
            sensors=data.get("sensors") or None,
            args=data.get("args") or None,
            skip_waits=bool(data.get("skip_waits", True)),
            timeout_ms=int(data.get("timeout_ms", 15000)),
            source=str(data.get("source", "")),
        )


@dataclass
class OqlResponse:
    """The result of executing OQL on a remote node."""

    correlation_id: str
    ok: bool
    result: dict[str, Any] | None = None
    error: str | None = None
    node_id: str = ""

    def to_json(self) -> str:
        payload = asdict(self)
        payload["v"] = ENVELOPE_VERSION
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str | bytes) -> "OqlResponse":
        data = json.loads(raw)
        return cls(
            correlation_id=str(data["correlation_id"]),
            ok=bool(data.get("ok", False)),
            result=data.get("result"),
            error=data.get("error"),
            node_id=str(data.get("node_id", "")),
        )


# ---------------------------------------------------------------------------
# paho compatibility (paho-mqtt 1.x vs 2.x)
# ---------------------------------------------------------------------------
def _make_client(client_id: str) -> mqtt.Client:
    """Construct a paho Client that works on both paho-mqtt 1.x and 2.x."""
    api_version = getattr(mqtt, "CallbackAPIVersion", None)
    if api_version is not None:  # paho-mqtt >= 2.0
        return mqtt.Client(
            callback_api_version=api_version.VERSION2,
            client_id=client_id or "",
        )
    return mqtt.Client(client_id=client_id or "")  # paho-mqtt 1.x


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------
class _PahoAsyncClient:
    """Wraps a paho client and bridges its network thread to an asyncio loop.

    Subclasses override :meth:`_subscriptions`, :meth:`_on_payload`, and
    optionally :meth:`_last_will`.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        node_id: str,
        topic_prefix: str = "oqlos/c2004",
        username: str | None = None,
        password: str | None = None,
        client_id: str | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._node_id = node_id
        self.topics = build_topics(topic_prefix, node_id)
        self._client = _make_client(client_id or f"oqlos-{node_id}-{uuid.uuid4().hex[:8]}")
        if username:
            self._client.username_pw_set(username, password or None)
        self._client.on_connect = self._handle_connect
        self._client.on_message = self._handle_message
        self._loop: asyncio.AbstractEventLoop | None = None
        self._connected = asyncio.Event()

    # -- lifecycle ------------------------------------------------------
    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        will = self._last_will()
        if will is not None:
            topic, payload, qos, retain = will
            self._client.will_set(topic, payload, qos=qos, retain=retain)
        self._client.connect(self._host, self._port, keepalive=60)
        self._client.loop_start()
        logger.info(
            "OQL MQTT %s connecting to %s:%s (node=%s)",
            type(self).__name__, self._host, self._port, self._node_id,
        )

    async def stop(self) -> None:
        try:
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:  # pragma: no cover - best-effort teardown
            logger.debug("OQL MQTT %s teardown error", type(self).__name__, exc_info=True)

    # -- overridable hooks ---------------------------------------------
    def _subscriptions(self) -> list[tuple[str, int]]:
        """Return ``[(topic, qos), ...]`` to subscribe on connect."""
        return []

    def _last_will(self) -> tuple[str, str, int, bool] | None:
        """Return ``(topic, payload, qos, retain)`` or ``None``."""
        return None

    def _on_payload(self, topic: str, payload: bytes) -> None:
        """Handle a received message. Runs on the asyncio loop thread."""

    # -- paho callbacks (run on the network thread) --------------------
    def _handle_connect(self, *args: Any) -> None:
        # paho 1.x: (client, userdata, flags, rc[, properties])
        # paho 2.x: (client, userdata, flags, reason_code, properties)
        for sub_topic, qos in self._subscriptions():
            self._client.subscribe(sub_topic, qos=qos)
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._connected.set)
        logger.info("OQL MQTT %s connected (node=%s)", type(self).__name__, self._node_id)

    def _handle_message(self, client: Any, userdata: Any, msg: Any) -> None:
        topic = msg.topic
        payload = msg.payload
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._on_payload, topic, payload)

    # -- helpers --------------------------------------------------------
    def _publish(self, topic: str, payload: str, *, qos: int = 1, retain: bool = False) -> None:
        self._client.publish(topic, payload, qos=qos, retain=retain)


# ---------------------------------------------------------------------------
# Controller (app node)
# ---------------------------------------------------------------------------
class OqlMqttController(_PahoAsyncClient):
    """Publishes OQL and awaits a correlated response."""

    def __init__(self, *, default_timeout_ms: int = 15000, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._default_timeout_ms = default_timeout_ms
        self._pending: dict[str, asyncio.Future] = {}
        self._event_listeners: list[asyncio.Queue] = []

    def _subscriptions(self) -> list[tuple[str, int]]:
        return [(self.topics.response_wildcard, 1), (self.topics.events, 0)]

    def _on_payload(self, topic: str, payload: bytes) -> None:
        if topic.startswith(self.topics.response_base + "/"):
            self._resolve_response(payload)
        elif topic == self.topics.events:
            self._fan_out_event(payload)

    def _resolve_response(self, payload: bytes) -> None:
        try:
            resp = OqlResponse.from_json(payload)
        except Exception:
            logger.warning("OQL controller got malformed response", exc_info=True)
            return
        fut = self._pending.get(resp.correlation_id)
        if fut is not None and not fut.done():
            fut.set_result(resp)

    def _fan_out_event(self, payload: bytes) -> None:
        try:
            event = json.loads(payload)
        except Exception:
            return
        for q in list(self._event_listeners):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:  # pragma: no cover - drop slow consumers
                pass

    async def execute(
        self,
        oql: str,
        *,
        kind: str = "command",
        mode: str = "execute",
        sensors: dict[str, float] | None = None,
        args: dict[str, Any] | None = None,
        skip_waits: bool = True,
        timeout: float | None = None,
        source: str = "controller",
    ) -> OqlResponse:
        """Publish a request and await its correlated response.

        Never raises on timeout — returns a synthetic ``ok=False`` response so
        callers always get a structured result.
        """
        if self._loop is None:
            raise RuntimeError("controller not started")
        timeout_s = timeout if timeout is not None else self._default_timeout_ms / 1000.0
        corr = uuid.uuid4().hex
        req = OqlRequest(
            correlation_id=corr,
            oql=oql,
            reply_to=self.topics.response_for(corr),
            kind=kind,
            mode=mode,
            sensors=sensors,
            args=args,
            skip_waits=skip_waits,
            timeout_ms=int(timeout_s * 1000),
            source=source,
        )
        fut: asyncio.Future = self._loop.create_future()
        self._pending[corr] = fut
        try:
            self._publish(self.topics.request, req.to_json(), qos=1)
            return await asyncio.wait_for(fut, timeout_s)
        except asyncio.TimeoutError:
            return OqlResponse(
                correlation_id=corr,
                ok=False,
                result=None,
                error=f"remote OQL execution timed out after {timeout_s:.1f}s",
                node_id=self._node_id,
            )
        finally:
            self._pending.pop(corr, None)

    async def manage(
        self,
        verb: str,
        args: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> OqlResponse:
        """Run a remote management/diagnostic verb (identify, health, recover, …)."""
        return await self.execute(verb, kind="manage", args=args, timeout=timeout, source="manage")

    def subscribe_events(self, maxsize: int = 256) -> asyncio.Queue:
        """Register a queue that receives agent event payloads (for /ws/oql)."""
        q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._event_listeners.append(q)
        return q

    def unsubscribe_events(self, q: asyncio.Queue) -> None:
        if q in self._event_listeners:
            self._event_listeners.remove(q)


# ---------------------------------------------------------------------------
# Agent (hardware Pi)
# ---------------------------------------------------------------------------
class OqlMqttAgent(_PahoAsyncClient):
    """Subscribes to OQL requests, executes them locally, and replies.

    ``gateway`` MUST be the already-initialized PluginHardwareGateway owned by the
    FastAPI app, so OQL execution reuses the open serial ports rather than
    constructing a second gateway (which would fail to open the same RS485/USB
    device twice).
    """

    def __init__(
        self,
        *,
        gateway: Any,
        firmware_url: str = LOCAL_FIRMWARE_URL,
        dedupe_ttl: int = 256,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._gateway = gateway
        self._firmware_url = firmware_url
        self._exec_lock = asyncio.Lock()
        self._seen: dict[str, None] = {}
        self._dedupe_ttl = dedupe_ttl

    def _subscriptions(self) -> list[tuple[str, int]]:
        return [(self.topics.request, 1)]

    def _last_will(self) -> tuple[str, str, int, bool]:
        offline = json.dumps({"node_id": self._node_id, "online": False})
        return (self.topics.status, offline, 1, True)

    async def start(self) -> None:
        await super().start()
        # Announce online (retained) once the loop is running.
        online = json.dumps({"node_id": self._node_id, "online": True})
        self._publish(self.topics.status, online, qos=1, retain=True)

    async def stop(self) -> None:
        offline = json.dumps({"node_id": self._node_id, "online": False})
        try:
            self._publish(self.topics.status, offline, qos=1, retain=True)
        except Exception:  # pragma: no cover
            pass
        await super().stop()

    def _on_payload(self, topic: str, payload: bytes) -> None:
        if topic != self.topics.request or self._loop is None:
            return
        try:
            req = OqlRequest.from_json(payload)
        except Exception:
            logger.warning("OQL agent got malformed request", exc_info=True)
            return
        # Schedule async handling on the loop.
        self._loop.create_task(self._handle_request(req))

    async def _handle_request(self, req: OqlRequest) -> None:
        # De-dupe QoS-1 redeliveries: actuating commands must not run twice.
        if req.correlation_id in self._seen:
            return
        self._seen[req.correlation_id] = None
        if len(self._seen) > self._dedupe_ttl:
            # Drop the oldest insertion (dict preserves insertion order).
            oldest = next(iter(self._seen))
            self._seen.pop(oldest, None)

        async with self._exec_lock:
            if req.kind == "manage":
                payload = await self._run_manage(req)
            else:
                payload = await asyncio.to_thread(self._run_oql, req)

        reply_topic = req.reply_to or self.topics.response_for(req.correlation_id)
        self._publish(reply_topic, payload.to_json(), qos=1)
        # Mirror the result onto the events stream for live observers.
        self._publish(
            self.topics.events,
            json.dumps({"correlation_id": req.correlation_id, "ok": payload.ok, "node_id": self._node_id}),
            qos=0,
        )

    async def _run_manage(self, req: OqlRequest) -> OqlResponse:
        """Run a management/diagnostic verb (async; uses the shared gateway)."""
        try:
            from oqlos.hardware.transport.manage_ops import run_manage_verb

            result = await run_manage_verb(req.oql, req.args)
            ok = bool(result.get("ok", True)) if isinstance(result, dict) else True
            return OqlResponse(req.correlation_id, ok=ok, result=result, node_id=self._node_id)
        except Exception as exc:  # never crash the agent loop
            logger.exception("OQL agent manage verb failed")
            return OqlResponse(req.correlation_id, ok=False, result=None, error=str(exc), node_id=self._node_id)

    def _run_oql(self, req: OqlRequest) -> OqlResponse:
        """Execute OQL synchronously (called inside a worker thread)."""
        try:
            if req.kind == "ping":
                return OqlResponse(req.correlation_id, ok=True, result={"pong": True}, node_id=self._node_id)

            from oqlos.tools.cql_cli.commands import run_single_command, run_source
            from oqlos.tools.cql_cli.utils import build_result_payload

            common = dict(
                mode=req.mode,
                quiet=True,
                sensors=req.sensors or {},
                firmware_url=self._firmware_url,
                skip_waits=req.skip_waits,
                gateway=self._gateway,
            )
            if req.kind == "script":
                result = run_source(req.oql, "<mqtt>", **common)
            else:
                result = run_single_command(req.oql, **common)

            payload = build_result_payload(result)
            return OqlResponse(req.correlation_id, ok=bool(payload.get("ok")), result=payload, node_id=self._node_id)
        except Exception as exc:  # never crash the agent loop
            logger.exception("OQL agent execution failed")
            return OqlResponse(req.correlation_id, ok=False, result=None, error=str(exc), node_id=self._node_id)
