"""CQRS + Event Sourcing primitives for OqlOS runtime state.

State (peripherals, execution status) is derived exclusively by replaying an
append-only EventStore through Aggregates; Projections are read models kept
in sync by subscribing to the same store. Writers never mutate state
directly — they dispatch a Command through a CommandBus, whose handler
turns validated intent into Events.
"""

from .aggregate import Aggregate
from .commands import Command, CommandBus
from .events import Event, EventStore
from .projection import Projection

__all__ = [
    "Aggregate",
    "Command",
    "CommandBus",
    "Event",
    "EventStore",
    "Projection",
    "build_command_bus",
]


def build_command_bus(store: EventStore) -> CommandBus:
    """Construct a CommandBus with every domain handler in this package registered."""
    from . import execution as _execution
    from . import peripheral as _peripheral

    bus = CommandBus(store)
    for command_type, handler in _peripheral.PERIPHERAL_HANDLERS.items():
        bus.register(command_type, handler)
    for command_type, handler in _execution.EXECUTION_HANDLERS.items():
        bus.register(command_type, handler)
    return bus
