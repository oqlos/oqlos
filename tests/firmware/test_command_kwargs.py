"""Tests for args/params command kwargs normalization."""

from __future__ import annotations

import pytest

from oqlos.api.command_kwargs import resolve_args_or_params, validate_args_or_params_types
from oqlos.api.hardware_lung import command_payload
from oqlos.errors import OqlosError


def test_resolve_prefers_nonempty_params_by_default():
    assert resolve_args_or_params(
        {"params": {"coil": 3}, "args": {"coil": 1}}
    ) == {"coil": 3}


def test_resolve_falls_back_to_args_when_params_empty():
    assert resolve_args_or_params(
        {"params": {}, "args": {"valve_id": "valve-4"}}
    ) == {"valve_id": "valve-4"}


def test_resolve_prefer_args_for_cqrs_style():
    assert resolve_args_or_params(
        {"params": {"a": 1}, "args": {"b": 2}},
        prefer="args",
    ) == {"b": 2}


def test_validate_rejects_non_object_args():
    with pytest.raises(ValueError, match="args"):
        validate_args_or_params_types({"args": "secret"})


def test_command_payload_accepts_params_alias():
    command, args = command_payload(
        {"command": "sync_to_system", "params": {"force": True}}
    )
    assert command == "sync_to_system"
    assert args == {"force": True}


def test_command_payload_still_rejects_string_args():
    with pytest.raises(OqlosError) as caught:
        command_payload({"command": "set_lpm", "args": "password=hunter2"})
    assert caught.value.detail["field"] == "args"
