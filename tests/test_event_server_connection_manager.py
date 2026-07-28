from __future__ import annotations

import pytest

from oqlos.shared.event_server import ConnectionManager, EventServerConnectionManager


class FakeWebSocket:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[str] = []

    async def send(self, message: str) -> None:
        if self.fail:
            raise ConnectionError("closed")
        self.messages.append(message)


@pytest.mark.asyncio
async def test_event_server_manager_keeps_legacy_alias_and_stats_schema() -> None:
    manager = ConnectionManager()
    websocket = FakeWebSocket()

    await manager.connect(websocket, {"source": "cli", "path": "/cli"})

    assert isinstance(manager, EventServerConnectionManager)
    assert manager.get_stats() == {
        "connections": 1,
        "clients": [{"source": "cli", "path": "/cli"}],
    }

    await manager.disconnect(websocket)
    assert manager.get_stats()["connections"] == 0


@pytest.mark.asyncio
async def test_event_server_manager_excludes_sender_and_prunes_failed_clients() -> None:
    manager = EventServerConnectionManager()
    sender = FakeWebSocket()
    receiver = FakeWebSocket()
    failed = FakeWebSocket(fail=True)
    for websocket in (sender, receiver, failed):
        await manager.connect(websocket)

    await manager.broadcast("event", exclude=sender)

    assert sender.messages == []
    assert receiver.messages == ["event"]
    assert failed not in manager.active
    assert failed not in manager.client_info
