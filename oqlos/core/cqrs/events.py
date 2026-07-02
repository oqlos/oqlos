"""Event sourcing primitives: immutable domain events and a replayable EventStore.

The EventStore is the single source of truth. Aggregates and projections never
receive direct attribute writes from callers — they exist only to replay and
fold the event stream into an in-memory shape.
"""

from __future__ import annotations

import dataclasses
import itertools
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True, kw_only=True)
class Event:
    """Base class for immutable domain events. Subclasses add their own fields."""

    stream_id: str
    version: int = -1
    timestamp: float = field(default_factory=time.time)

    @property
    def event_type(self) -> str:
        return type(self).__name__


Subscriber = Callable[[Event], None]


class EventStore:
    """Append-only, replayable event store.

    `append` assigns the next per-stream version and notifies subscribers
    synchronously; `replay` reconstructs a stream's full history in order.
    """

    def __init__(self) -> None:
        self._streams: dict[str, list[Event]] = {}
        self._subscribers: list[Subscriber] = []
        self._lock = threading.Lock()

    def append(self, event: Event) -> Event:
        with self._lock:
            stream = self._streams.setdefault(event.stream_id, [])
            versioned = dataclasses.replace(event, version=len(stream))
            stream.append(versioned)
        for subscriber in self._subscribers:
            subscriber(versioned)
        return versioned

    def append_many(self, events: list[Event]) -> list[Event]:
        return [self.append(event) for event in events]

    def replay(self, stream_id: str) -> list[Event]:
        with self._lock:
            return list(self._streams.get(stream_id, ()))

    def all_events(self) -> list[Event]:
        with self._lock:
            return list(itertools.chain.from_iterable(self._streams.values()))

    def stream_ids(self) -> list[str]:
        with self._lock:
            return list(self._streams.keys())

    def subscribe(self, subscriber: Subscriber) -> None:
        """Register a callback invoked synchronously after every append (for projections)."""
        self._subscribers.append(subscriber)
