"""Event-sourced Peripheral aggregate: value/mode/status changes only happen via commands.

StateManager.peripherals is a Projection folded from this stream — nothing
outside this module is allowed to write to a Peripheral's fields directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from oqlos.models.peripheral import Peripheral, PeripheralMode, PeripheralStatus, PeripheralType

from .aggregate import Aggregate
from .commands import Command
from .events import Event
from .projection import Projection

# --- Events ------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class PeripheralRegistered(Event):
    type: PeripheralType
    name: str
    currentValue: Any
    targetValue: Any
    unit: str | None = None
    range: dict[str, float] | None = None
    status: PeripheralStatus = PeripheralStatus.OK
    mode: PeripheralMode = PeripheralMode.AUTO
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True)
class PeripheralValueSet(Event):
    current_value: Any
    target_value: Any


@dataclass(frozen=True, kw_only=True)
class PeripheralModeChanged(Event):
    mode: PeripheralMode


@dataclass(frozen=True, kw_only=True)
class PeripheralStatusChanged(Event):
    status: PeripheralStatus


# --- Aggregate -----------------------------------------------------------------


class PeripheralAggregate(Aggregate):
    """Rehydrates a single Peripheral's current shape by replaying its event stream."""

    def __init__(self, aggregate_id: str) -> None:
        super().__init__(aggregate_id)
        self.peripheral: Peripheral | None = None

    def apply(self, event: Event) -> None:
        if isinstance(event, PeripheralRegistered):
            self.peripheral = Peripheral(
                id=self.aggregate_id,
                type=event.type,
                name=event.name,
                currentValue=event.currentValue,
                targetValue=event.targetValue,
                unit=event.unit,
                range=event.range,
                status=event.status,
                mode=event.mode,
                dependencies=list(event.dependencies),
            )
        elif self.peripheral is None:
            return  # Ignore events for a peripheral that was never registered.
        elif isinstance(event, PeripheralValueSet):
            self.peripheral = self.peripheral.model_copy(
                update={"currentValue": event.current_value, "targetValue": event.target_value}
            )
        elif isinstance(event, PeripheralModeChanged):
            self.peripheral = self.peripheral.model_copy(update={"mode": event.mode})
        elif isinstance(event, PeripheralStatusChanged):
            self.peripheral = self.peripheral.model_copy(update={"status": event.status})


# --- Commands --------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class RegisterPeripheralCommand(Command):
    peripheral_id: str
    type: PeripheralType
    name: str
    currentValue: Any = None
    targetValue: Any = None
    unit: str | None = None
    range: dict[str, float] | None = None
    status: PeripheralStatus = PeripheralStatus.OK
    mode: PeripheralMode = PeripheralMode.AUTO
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True)
class SetPeripheralValueCommand(Command):
    peripheral_id: str
    current_value: Any
    target_value: Any


@dataclass(frozen=True, kw_only=True)
class SetPeripheralModeCommand(Command):
    peripheral_id: str
    mode: PeripheralMode


@dataclass(frozen=True, kw_only=True)
class SetPeripheralStatusCommand(Command):
    peripheral_id: str
    status: PeripheralStatus


def handle_register_peripheral(cmd: RegisterPeripheralCommand) -> list[Event]:
    return [
        PeripheralRegistered(
            stream_id=cmd.peripheral_id,
            type=cmd.type,
            name=cmd.name,
            currentValue=cmd.currentValue,
            targetValue=cmd.targetValue,
            unit=cmd.unit,
            range=cmd.range,
            status=cmd.status,
            mode=cmd.mode,
            dependencies=cmd.dependencies,
        )
    ]


def handle_set_peripheral_value(cmd: SetPeripheralValueCommand) -> list[Event]:
    return [
        PeripheralValueSet(
            stream_id=cmd.peripheral_id,
            current_value=cmd.current_value,
            target_value=cmd.target_value,
        )
    ]


def handle_set_peripheral_mode(cmd: SetPeripheralModeCommand) -> list[Event]:
    return [PeripheralModeChanged(stream_id=cmd.peripheral_id, mode=cmd.mode)]


def handle_set_peripheral_status(cmd: SetPeripheralStatusCommand) -> list[Event]:
    return [PeripheralStatusChanged(stream_id=cmd.peripheral_id, status=cmd.status)]


PERIPHERAL_HANDLERS: dict[type[Command], object] = {
    RegisterPeripheralCommand: handle_register_peripheral,
    SetPeripheralValueCommand: handle_set_peripheral_value,
    SetPeripheralModeCommand: handle_set_peripheral_mode,
    SetPeripheralStatusCommand: handle_set_peripheral_status,
}


# --- Projection (read model) ------------------------------------------------


class PeripheralsProjection(Projection):
    """Read model: `peripherals[id]` mirrors the latest replayed state of each stream."""

    def __init__(self) -> None:
        self.peripherals: dict[str, Peripheral] = {}
        self._aggregates: dict[str, PeripheralAggregate] = {}

    def apply(self, event: Event) -> None:
        if not isinstance(
            event,
            (PeripheralRegistered, PeripheralValueSet, PeripheralModeChanged, PeripheralStatusChanged),
        ):
            return
        aggregate = self._aggregates.setdefault(event.stream_id, PeripheralAggregate(event.stream_id))
        aggregate.apply(event)
        if aggregate.peripheral is not None:
            self.peripherals[event.stream_id] = aggregate.peripheral
