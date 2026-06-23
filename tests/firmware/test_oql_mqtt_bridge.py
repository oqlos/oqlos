"""Controller<->agent OQL round-trips over an in-memory loopback broker.

No real MQTT broker and no real hardware: a ``FakeBroker`` routes ``publish`` to
matching subscribers synchronously, and the agent runs OQL in ``dry-run`` against
an injected mock gateway.
"""

from __future__ import annotations

import asyncio

import pytest

from oqlos.hardware.plugin_gateway import PluginHardwareGateway
from oqlos.hardware.transport import OqlRequest, mqtt_oql_bridge
from oqlos.hardware.transport.mqtt_oql_bridge import OqlMqttAgent, OqlMqttController


# --------------------------------------------------------------------------
# In-memory fake paho broker
# --------------------------------------------------------------------------
def _topic_matches(filt: str, topic: str) -> bool:
    fp, tp = filt.split("/"), topic.split("/")
    i = 0
    for i, seg in enumerate(fp):
        if seg == "#":
            return True
        if i >= len(tp):
            return False
        if seg == "+":
            continue
        if seg != tp[i]:
            return False
    return len(fp) == len(tp)


class _FakeMessage:
    def __init__(self, topic: str, payload: bytes):
        self.topic = topic
        self.payload = payload


class FakeBroker:
    def __init__(self):
        self.clients: list["FakeClient"] = []
        self.retained: dict[str, bytes] = {}

    def register(self, client: "FakeClient") -> None:
        self.clients.append(client)

    def publish(self, topic: str, payload, qos=0, retain=False) -> None:
        data = payload.encode() if isinstance(payload, str) else payload
        if retain:
            self.retained[topic] = data
        for client in self.clients:
            for filt in client.subscriptions:
                if _topic_matches(filt, topic) and client.on_message is not None:
                    client.on_message(client, None, _FakeMessage(topic, data))
                    break

    def deliver_retained(self, client: "FakeClient", filt: str) -> None:
        for topic, data in self.retained.items():
            if _topic_matches(filt, topic) and client.on_message is not None:
                client.on_message(client, None, _FakeMessage(topic, data))


class FakeClient:
    def __init__(self, broker: FakeBroker, client_id: str = ""):
        self._broker = broker
        self.client_id = client_id
        self.on_connect = None
        self.on_message = None
        self.subscriptions: set[str] = set()
        self._will = None
        broker.register(self)

    def username_pw_set(self, username, password=None):
        pass

    def will_set(self, topic, payload, qos=0, retain=False):
        self._will = (topic, payload, qos, retain)

    def connect(self, host, port, keepalive=60):
        if self.on_connect is not None:
            self.on_connect(self, None, {}, 0)

    def loop_start(self):
        pass

    def loop_stop(self):
        pass

    def disconnect(self):
        pass

    def subscribe(self, topic, qos=0):
        self.subscriptions.add(topic)
        self._broker.deliver_retained(self, topic)

    def publish(self, topic, payload, qos=0, retain=False):
        self._broker.publish(topic, payload, qos=qos, retain=retain)


@pytest.fixture
def broker(monkeypatch):
    b = FakeBroker()
    monkeypatch.setattr(mqtt_oql_bridge, "_make_client", lambda client_id="": FakeClient(b, client_id))
    return b


async def _make_pair(broker, *, with_agent=True):
    common = dict(host="localhost", port=1883, node_id="pi-hw", topic_prefix="oqlos/c2004")
    controller = OqlMqttController(default_timeout_ms=2000, **common)
    await controller.start()
    agent = None
    if with_agent:
        agent = OqlMqttAgent(gateway=PluginHardwareGateway(mode="mock"), **common)
        await agent.start()
    return controller, agent


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ping_round_trip(broker):
    controller, agent = await _make_pair(broker)
    try:
        resp = await controller.execute("", kind="ping", timeout=2.0)
        assert resp.ok is True
        assert resp.result == {"pong": True}
        assert resp.node_id == "pi-hw"
    finally:
        await agent.stop()
        await controller.stop()


@pytest.mark.asyncio
async def test_command_round_trip_executes_oql(broker):
    controller, agent = await _make_pair(broker)
    try:
        resp = await controller.execute("SET 'VALVE-NC' 'open'", mode="dry-run", timeout=2.0)
        assert resp.ok is True
        assert resp.result is not None
        assert resp.result["passed"] == 1
        assert resp.result["failed"] == 0
    finally:
        await agent.stop()
        await controller.stop()


@pytest.mark.asyncio
async def test_concurrent_requests_resolve_their_own_correlation(broker):
    controller, agent = await _make_pair(broker)
    try:
        results = await asyncio.gather(
            controller.execute("", kind="ping", timeout=2.0),
            controller.execute("SET 'VALVE-NC' 'open'", mode="dry-run", timeout=2.0),
            controller.execute("", kind="ping", timeout=2.0),
        )
        assert all(r.ok for r in results)
        corr_ids = {r.correlation_id for r in results}
        assert len(corr_ids) == 3  # each call got its own correlation id back
    finally:
        await agent.stop()
        await controller.stop()


@pytest.mark.asyncio
async def test_timeout_when_no_agent_replies(broker):
    controller, _ = await _make_pair(broker, with_agent=False)
    try:
        resp = await controller.execute("", kind="ping", timeout=0.2)
        assert resp.ok is False
        assert "timed out" in (resp.error or "")
    finally:
        await controller.stop()


@pytest.mark.asyncio
async def test_manage_verb_round_trip(broker):
    from oqlos.api.hardware import set_hardware_gateway

    gw = PluginHardwareGateway(mode="mock")
    set_hardware_gateway(gw)
    common = dict(host="localhost", port=1883, node_id="pi-hw", topic_prefix="oqlos/c2004")
    controller = OqlMqttController(default_timeout_ms=2000, **common)
    await controller.start()
    agent = OqlMqttAgent(gateway=gw, **common)
    await agent.start()
    try:
        resp = await controller.manage("health", timeout=2.0)
        assert resp.ok is True
        assert isinstance(resp.result, dict)
        assert "mode" in resp.result
    finally:
        await agent.stop()
        await controller.stop()


@pytest.mark.asyncio
async def test_manage_unknown_verb_is_ok_false(broker):
    from oqlos.api.hardware import set_hardware_gateway

    gw = PluginHardwareGateway(mode="mock")
    set_hardware_gateway(gw)
    common = dict(host="localhost", port=1883, node_id="pi-hw", topic_prefix="oqlos/c2004")
    controller = OqlMqttController(default_timeout_ms=2000, **common)
    await controller.start()
    agent = OqlMqttAgent(gateway=gw, **common)
    await agent.start()
    try:
        resp = await controller.manage("does-not-exist", timeout=2.0)
        assert resp.ok is False
        assert "unknown manage verb" in (resp.error or "")
    finally:
        await agent.stop()
        await controller.stop()


@pytest.mark.asyncio
async def test_agent_run_oql_handles_execution_errors(broker, monkeypatch):
    _, agent = await _make_pair(broker)
    try:
        # If execution raises, the agent must report ok=False rather than crash.
        def _boom(*args, **kwargs):
            raise RuntimeError("serial port busy")

        monkeypatch.setattr(
            "oqlos.tools.cql_cli.commands.run_single_command", _boom, raising=True
        )
        bad = OqlRequest(correlation_id="x", oql="SET 'VALVE-NC' 'open'", mode="dry-run")
        resp = agent._run_oql(bad)
        assert resp.correlation_id == "x"
        assert resp.ok is False
        assert "serial port busy" in (resp.error or "")
    finally:
        await agent.stop()
