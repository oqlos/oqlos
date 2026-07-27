"""Regression tests for disabled runtime-python hardware route."""

from __future__ import annotations

import asyncio

import pytest

from oqlos.api._hw3_system import hardware_runtime_python_v3
from oqlos.errors import OqlosError


def test_runtime_python_raises_typed_disabled_error():
    with pytest.raises(OqlosError) as caught:
        asyncio.run(hardware_runtime_python_v3({"code": "print(1)"}))
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.issue_code == "api_oql_transport_disabled"
    assert caught.value.detail["received"]["code"] == "print(1)"
