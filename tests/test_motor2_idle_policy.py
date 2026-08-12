"""Regression tests for the Tic249 deenergized idle policy."""

from __future__ import annotations

from typing import Any

import oqlos.core._action_motor2 as motor2_actions


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _Client:
    def __init__(self, calls: list[tuple[str, dict[str, Any] | None]]) -> None:
        self.calls = calls

    def __enter__(self) -> "_Client":
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def post(self, path: str, json: dict[str, Any] | None = None) -> _Response:
        self.calls.append((path, json))
        return _Response({"success": True})


def test_motor2_stop_halts_motion_then_releases_coils(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, Any] | None]] = []
    monkeypatch.setattr(
        motor2_actions.httpx,
        "Client",
        lambda **_kwargs: _Client(calls),
    )

    motor2_actions._post_motor2_stop()

    assert calls == [
        ("/api/stop", {"stop_mode": "reach_limit"}),
    ]
