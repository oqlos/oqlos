"""Aggregate base: reconstructs its state purely by replaying events from an EventStore."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from .events import Event, EventStore

A = TypeVar("A", bound="Aggregate")


class Aggregate(ABC):
    """Base for event-sourced aggregates.

    Subclasses implement `apply()` to fold one event into their in-memory
    state. `apply()` is the ONLY place that state changes — there is no
    public setter, so state can only ever be reached by replaying events.
    """

    def __init__(self, aggregate_id: str) -> None:
        self.aggregate_id = aggregate_id
        self.version = -1

    @abstractmethod
    def apply(self, event: Event) -> None:
        """Mutate in-memory state to reflect *event*."""

    def load(self, store: EventStore) -> None:
        for event in store.replay(self.aggregate_id):
            self.apply(event)
            self.version = event.version

    @classmethod
    def rehydrate(cls: type[A], aggregate_id: str, store: EventStore) -> A:
        """Build a fresh aggregate instance by replaying its full event history."""
        aggregate = cls(aggregate_id)
        aggregate.load(store)
        return aggregate
