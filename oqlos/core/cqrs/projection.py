"""Projection base: a read model kept in sync by consuming the event stream."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .events import Event, EventStore


class Projection(ABC):
    """Read-model base. Subscribes to an EventStore and folds matching events."""

    @abstractmethod
    def apply(self, event: Event) -> None:
        """Update the read model to reflect *event*. Ignore event types it doesn't care about."""

    def rebuild(self, store: EventStore) -> None:
        """Rebuild the projection from scratch by replaying every event in the store."""
        for event in store.all_events():
            self.apply(event)

    def attach(self, store: EventStore) -> None:
        """Catch up on history, then subscribe to future events."""
        self.rebuild(store)
        store.subscribe(self.apply)
