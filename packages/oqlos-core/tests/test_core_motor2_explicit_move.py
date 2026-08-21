"""Execution contract for bounded Tic249 installation jogs."""

from __future__ import annotations

from typing import Any

from oqlos.core import _action_motor2


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _Client:
    def __init__(self) -> None:
        self.posts: list[tuple[str, dict[str, Any] | None]] = []
        self.statuses = iter([
            {
                "connected": True,
                "position": 1_000,
                "velocity": 0,
                "forward_limit_active": False,
                "reverse_limit_active": False,
            },
            {
                "connected": True,
                "position": 1_040,
                "velocity": 400_000,
                "forward_limit_active": False,
                "reverse_limit_active": False,
            },
            {
                "connected": True,
                "position": 1_100,
                "velocity": 0,
                "forward_limit_active": False,
                "reverse_limit_active": False,
            },
        ])

    def __enter__(self) -> "_Client":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def get(self, path: str) -> _Response:
        assert path == "/api/status"
        return _Response(next(self.statuses))

    def post(self, path: str, json: dict[str, Any] | None = None) -> _Response:
        self.posts.append((path, json))
        return _Response({"success": True, "offset": 100})


def test_explicit_move_waits_until_bounded_target_is_reached(monkeypatch) -> None:
    client = _Client()
    monkeypatch.setattr(_action_motor2, "lung_motor_url", lambda: "http://tic249")
    monkeypatch.setattr(_action_motor2.httpx, "Client", lambda **_kwargs: client)
    monkeypatch.setattr(_action_motor2.time, "sleep", lambda _seconds: None)

    _action_motor2._post_motor2_move_relative("right", 100, 1_000_000, None)

    assert client.posts == [
        ("/api/move-relative", {"offset": 100, "speed": 1_000_000}),
    ]
