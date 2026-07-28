from __future__ import annotations

from dataclasses import dataclass

import pytest

from oqlos.core.cqrs import CommandBus, EventSourcedCommandBus
from oqlos.core.cqrs.commands import Command
from oqlos.core.cqrs.events import Event, EventStore


@dataclass(frozen=True, kw_only=True)
class RenameDevice(Command):
    device_id: str
    name: str


@dataclass(frozen=True, kw_only=True)
class DeviceRenamed(Event):
    name: str


def test_event_sourced_command_bus_keeps_legacy_alias_and_persists_events() -> None:
    store = EventStore()
    bus = CommandBus(store)
    bus.register(
        RenameDevice,
        lambda command: [
            DeviceRenamed(stream_id=command.device_id, name=command.name),
        ],
    )

    persisted = bus.dispatch(RenameDevice(device_id="device-1", name="Valve"))

    assert isinstance(bus, EventSourcedCommandBus)
    assert persisted == store.replay("device-1")
    assert persisted[0].version == 0
    assert persisted[0].name == "Valve"


def test_event_sourced_command_bus_rejects_unregistered_command() -> None:
    bus = EventSourcedCommandBus(EventStore())

    with pytest.raises(LookupError, match="No handler registered for RenameDevice"):
        bus.dispatch(RenameDevice(device_id="device-1", name="Valve"))
