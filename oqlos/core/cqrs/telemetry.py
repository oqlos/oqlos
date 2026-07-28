"""Event-sourced sensor telemetry: an audit trail for real hardware readings.

Unlike PeripheralAggregate/ExecutionAggregate, this is *additive* — OqlInterpreter's
in-memory `sensor_values` dict remains the authoritative value for a running
script (it's local execution state, not shared domain state; see the module
docstring discussion that led to this design). This module only records what
was actually observed on real hardware (`mode="execute"`) as immutable events,
giving a genuine CQRS query side: "what did sensor X read, and when?".
"""

from __future__ import annotations

from dataclasses import dataclass

from .events import Event, EventStore
from .projection import Projection

# --- Events ------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class SensorObserved(Event):
    value: float
    source: str = "firmware"


# --- Recording (write side) -------------------------------------------------


def record_sensor_readings(store: EventStore, readings: dict[str, float], *, source: str = "firmware") -> None:
    """Append one SensorObserved event per reading. No-op if *store* is None."""
    if store is None:
        return
    for sensor_id, value in readings.items():
        try:
            store.append(SensorObserved(stream_id=sensor_id, value=float(value), source=source))
        except (TypeError, ValueError):
            continue  # Skip non-numeric readings; they aren't telemetry facts.


# --- Query side (read model) ------------------------------------------------


class SensorTelemetryProjection(Projection):
    """Read model: `latest[sensor_id]` and full per-sensor history."""

    def __init__(self) -> None:
        self.latest: dict[str, float] = {}

    def apply(self, event: Event) -> None:
        if isinstance(event, SensorObserved):
            self.latest[event.stream_id] = event.value


def latest_sensor_values(store: EventStore) -> dict[str, float]:
    """Query: current best-known value per sensor, derived from the event log."""
    projection = SensorTelemetryProjection()
    projection.rebuild(store)
    return projection.latest


def sensor_history(store: EventStore, sensor_id: str) -> list[SensorObserved]:
    """Query: every recorded observation for *sensor_id*, oldest first."""
    return [event for event in store.replay(sensor_id) if isinstance(event, SensorObserved)]
