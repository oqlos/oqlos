"""Regression tests for shared HardwareGateway accessors."""

from __future__ import annotations

import pytest

from oqlos.api import hardware_gateway as gateway
from oqlos.errors import OqlosError


def test_get_hardware_gateway_raises_typed_error_when_uninitialised(monkeypatch):
    monkeypatch.setattr(gateway, "_gateway", None)

    with pytest.raises(OqlosError) as caught:
        gateway.get_hardware_gateway()
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "config_unavailable"
