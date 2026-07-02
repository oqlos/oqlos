# oqlos/shared/event_store.py
"""
Append-only EventStore with optional JSON file persistence.

Consolidates the event store originally from c2004/dsl.

Usage:
    from oqlos.shared.event_store import EventStore

    store = EventStore()                          # in-memory
    store = EventStore(persist_path="events.json") # with persistence
"""

import json
import os
from typing import Dict


class EventStore:
    """Append-only event store with optional JSON file persistence."""

    def __init__(self, persist_path: str | None = None):
        self.events: list[Dict] = []
        self.persist_path = persist_path

        if persist_path and os.path.exists(persist_path):
            self._load()

    def append(self, event: Dict) -> None:
        """Append an event to the store."""
        self.events.append(event)
        if self.persist_path:
            self._save()

    def get_all(self) -> list[Dict]:
        """Return a copy of all events."""
        return self.events.copy()

    def get_recent(self, limit: int = 100) -> list[Dict]:
        """Return the most recent *limit* events."""
        return self.events[-limit:]

    def get_by_correlation(self, correlation_id: str) -> list[Dict]:
        """Filter events by correlationId."""
        return [e for e in self.events if e.get('correlationId') == correlation_id]

    def clear(self) -> None:
        """Remove all events."""
        self.events = []
        if self.persist_path:
            self._save()

    def to_json(self) -> str:
        """Serialize events to JSON string."""
        return json.dumps(self.events, indent=2)

    def from_json(self, data: str) -> None:
        """Load events from a JSON string."""
        self.events = json.loads(data)

    @property
    def count(self) -> int:
        return len(self.events)

    # -- persistence helpers --------------------------------------------------

    def _save(self) -> None:
        if self.persist_path:
            with open(self.persist_path, 'w') as f:
                json.dump(self.events, f)

    def _load(self) -> None:
        try:
            with open(self.persist_path, 'r') as f:  # type: ignore
                self.events = json.load(f)
        except Exception:
            self.events = []
