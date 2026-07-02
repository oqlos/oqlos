"""Command base and a synchronous CommandBus dispatching to registered handlers.

A command expresses intent; a handler validates it and returns the events
that intent produces. The bus appends those events to the EventStore —
callers never mutate aggregate/projection state directly.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from .events import Event, EventStore


@dataclass(frozen=True, kw_only=True)
class Command:
    """Base class for commands: an intent to change state."""


C = TypeVar("C", bound=Command)
Handler = Callable[[C], list[Event]]


class CommandBus:
    """Dispatches a command to its registered handler and persists the resulting events."""

    def __init__(self, store: EventStore) -> None:
        self._store = store
        self._handlers: dict[type, Handler] = {}

    def register(self, command_type: type[C], handler: Handler) -> None:
        self._handlers[command_type] = handler

    def dispatch(self, command: Command) -> list[Event]:
        handler = self._handlers.get(type(command))
        if handler is None:
            raise LookupError(f"No handler registered for {type(command).__name__}")
        return self._store.append_many(handler(command))
