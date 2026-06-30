"""Tests for shared Tic249 unit conversions."""

from oqlos.hardware.tic249_units import (
    TIC249_DEFAULT_TARGET_VELOCITY,
    raw_acceleration_for_ramp,
    steps_per_second_to_raw,
)


def test_steps_per_second_to_raw_default_cap() -> None:
    assert steps_per_second_to_raw(1000) == 10_000_000
    assert steps_per_second_to_raw(10_000, max_steps_per_second=10_000) == 100_000_000
    assert steps_per_second_to_raw(20_000, max_steps_per_second=10_000) == 100_000_000


def test_raw_acceleration_for_ramp() -> None:
    assert raw_acceleration_for_ramp(TIC249_DEFAULT_TARGET_VELOCITY, 0.5) == 20_000_000
